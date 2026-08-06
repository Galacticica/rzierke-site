'''
File: fetch_watch_metadata.py
Project: rzierke-site
Description: Backfill watch-order entries with release year, runtime, and
episode counts from TMDB. Blank fields only unless --overwrite is passed, so
anything entered by hand is safe. Needs TMDB_API_KEY in .env:

	uv run python manage.py fetch_watch_metadata
	uv run python manage.py fetch_watch_metadata --overwrite --track fox-x-men
'''

from django.core.management.base import BaseCommand, CommandError

from connections import tmdb
from connections.models import WatchEntry
from connections.watch_order_service import WatchOrderService


class Command(BaseCommand):
	help = "Fill in watch-order metadata (year, runtime, episode count) from TMDB."

	def add_arguments(self, parser):
		parser.add_argument(
			"--overwrite",
			action="store_true",
			help="Replace values that are already set, not just the blank ones.",
		)
		parser.add_argument(
			"--track",
			help="Limit to one track, by slug.",
		)
		parser.add_argument(
			"--dry-run",
			action="store_true",
			help="Report what would change without saving.",
		)

	def handle(self, *args, **options):
		if not tmdb.is_configured():
			raise CommandError(
				"TMDB_API_KEY is not set. Add a TMDB API key to your .env to enable lookups."
			)

		entries = WatchEntry.objects.select_related("track").order_by("track__lane_order", "position")
		if options["track"]:
			entries = entries.filter(track__slug=options["track"])
			if not entries.exists():
				raise CommandError(f"No entries in a track with slug '{options['track']}'.")

		updated, skipped, failed = 0, 0, []
		for entry in entries:
			try:
				changed = tmdb.apply_to_entry(
					entry, overwrite=options["overwrite"], save=not options["dry_run"]
				)
			except tmdb.TMDBError as error:
				failed.append((entry, str(error)))
				self.stdout.write(self.style.WARNING(f"  ! {entry.title}: {error}"))
				continue

			if changed:
				updated += 1
				self.stdout.write(f"  {entry.title} -> {', '.join(changed)}")
			else:
				skipped += 1

		self.stdout.write("")
		self.stdout.write(self.style.SUCCESS(f"{updated} updated, {skipped} already complete, {len(failed)} failed."))

		if options["dry_run"]:
			self.stdout.write(self.style.NOTICE("Dry run - nothing was saved."))
		elif updated:
			WatchOrderService.invalidate_cache()
