'''
File: dump_watch_order.py
Project: rzierke-site
Description: Print the watch-order graph as text - lanes, list order, and every
stated prerequisite - so a layout problem can be reproduced from real data
instead of guessed at. Read-only.

	uv run python manage.py dump_watch_order
	uv run python manage.py dump_watch_order --track netflix
	fly ssh console -C "python /app/manage.py dump_watch_order"
'''

from django.core.management.base import BaseCommand

from connections.models import WatchEntry, WatchTrack
from connections.watch_order_service import WatchOrderService


class Command(BaseCommand):
	help = "Print the watch-order structure: lanes, order, and prerequisites."

	def add_arguments(self, parser):
		parser.add_argument("--track", help="Limit to one track, by slug.")

	def handle(self, *args, **options):
		service = WatchOrderService()
		tracks = list(WatchTrack.objects.filter(is_active=True).select_related("continues_from"))
		columns = service._columns(tracks)

		lanes = {}
		for lane, chain in enumerate(columns):
			for track in chain:
				lanes[track.slug] = lane

		self.stdout.write("LANES (tracks sharing a lane are stacked in one column)")
		for lane, chain in enumerate(columns):
			names = " -> ".join(track.name for track in chain)
			self.stdout.write(f"  lane {lane}: {names}")

		entries = (
			WatchEntry.objects.filter(is_published=True, track__is_active=True)
			.select_related("track")
			.prefetch_related("prerequisites__track")
		)
		if options["track"]:
			entries = entries.filter(track__slug=options["track"])

		ordered = sorted(entries, key=lambda item: (lanes.get(item.track.slug, 0), item.position, item.pk))

		self.stdout.write("")
		self.stdout.write("ENTRIES (in the order the chart reads them)")
		self.stdout.write(f"{'#':>4}  {'lane':>4}  {'position':>12}  title")

		fan_in, fan_out = {}, {}
		for index, entry in enumerate(ordered, start=1):
			lane = lanes.get(entry.track.slug, 0)
			self.stdout.write(f"{index:>4}  {lane:>4}  {entry.position:>12}  {entry.title}")

			prerequisites = list(entry.prerequisites.all())
			if prerequisites:
				for prerequisite in prerequisites:
					same = "same lane" if lanes.get(prerequisite.track.slug) == lane else "OTHER LANE"
					self.stdout.write(f"{'':>24}  after: {prerequisite.title}  [{same}]")
					fan_out.setdefault(prerequisite.title, []).append(entry.title)
				fan_in.setdefault(entry.title, [item.title for item in prerequisites])

			if not entry.connects_to_previous:
				self.stdout.write(f"{'':>24}  (no arrow from the previous entry)")

		self.stdout.write("")
		self.stdout.write("FANS (what should end up side by side)")
		for title, sources in fan_in.items():
			if len(sources) > 1:
				self.stdout.write(f"  {len(sources)} -> {title}: {', '.join(sources)}")
		for title, targets in fan_out.items():
			if len(targets) > 1:
				self.stdout.write(f"  {title} -> {len(targets)}: {', '.join(targets)}")

		self.stdout.write("")
		self.stdout.write(f"{len(ordered)} entries, {len(fan_in)} with stated prerequisites.")
