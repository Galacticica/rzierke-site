'''
File: link_watch_posters.py
Project: rzierke-site
Description: Match WatchEntry rows to the poster files committed under
static/public/watch-order/, and report the ones that still have no image.

Entries added from production start with no poster, so this is the command that
closes the loop after the image file lands in the repo. Read-only by default;
pass --apply to write the unambiguous matches:

	uv run python manage.py link_watch_posters
	uv run python manage.py link_watch_posters --apply
'''

from django.core.management.base import BaseCommand

from connections.models import WatchEntry
from connections.poster_matching import (
	POSTER_DIR,
	POSTER_PREFIX,
	poster_files,
	poster_index,
	resolve_poster,
)
from connections.watch_order_service import WatchOrderService


class Command(BaseCommand):
	help = "Match watch-order entries to committed poster files and report what is missing."

	def add_arguments(self, parser):
		parser.add_argument(
			"--apply",
			action="store_true",
			help="Write the unambiguous matches to poster_path (default is a dry run).",
		)

	def handle(self, *args, **options):
		if not POSTER_DIR.is_dir():
			self.stdout.write(self.style.ERROR(f"No poster directory at {POSTER_DIR}"))
			return

		files = poster_files()
		by_key = poster_index()

		matched, ambiguous, missing = [], [], []
		used = set()

		for entry in WatchEntry.objects.select_related("track").order_by("track__lane_order", "position"):
			if entry.poster_path:
				used.add(entry.poster_path.removeprefix(POSTER_PREFIX))
				continue

			poster_path, tied = resolve_poster(entry.title, entry.release_year, by_key)
			if poster_path:
				name = poster_path.removeprefix(POSTER_PREFIX)
				matched.append((entry, name))
				used.add(name)
			elif tied:
				ambiguous.append((entry, tied))
			else:
				missing.append(entry)

		self._report(matched, ambiguous, missing, files, used, options["apply"])

	def _report(self, matched, ambiguous, missing, files, used, apply_changes):
		if matched:
			self.stdout.write(self.style.SUCCESS(f"\n{len(matched)} entr(ies) matched a poster file:"))
			for entry, name in matched:
				self.stdout.write(f"  {entry.title} -> {name}")

		if ambiguous:
			self.stdout.write(self.style.WARNING(f"\n{len(ambiguous)} ambiguous (pick one by hand):"))
			for entry, candidates in ambiguous:
				names = ", ".join(path.name for path in candidates)
				self.stdout.write(f"  {entry.title} -> {names}")

		if missing:
			self.stdout.write(self.style.WARNING(f"\n{len(missing)} entr(ies) with no poster file:"))
			for entry in missing:
				self.stdout.write(f"  {entry.title} ({entry.track.name})")

		orphans = [path.name for path in files if path.name not in used]
		if orphans:
			self.stdout.write(self.style.NOTICE(f"\n{len(orphans)} poster file(s) no entry references:"))
			for name in orphans:
				self.stdout.write(f"  {name}")

		if not apply_changes:
			if matched:
				self.stdout.write(self.style.NOTICE("\nDry run. Re-run with --apply to write these."))
			return

		for entry, name in matched:
			entry.poster_path = POSTER_PREFIX + name
			entry.save(update_fields=["poster_path"])

		WatchOrderService.invalidate_cache()
		self.stdout.write(self.style.SUCCESS(f"\nWrote poster_path on {len(matched)} entr(ies)."))
