'''
File: find_orphaned_images.py
Project: rzierke-site
Description: List objects in the Tigris connections bucket that no Character
references -- orphans left behind after a character is renamed or deleted.
Read-only by default; pass --delete to remove them. Local-only tool (needs the
Tigris keys in .env), mirror of sync_character_images:

	uv run python manage.py find_orphaned_images
	uv run python manage.py find_orphaned_images --delete
'''

import os

from django.core.management.base import BaseCommand, CommandError

ENDPOINT_URL = os.getenv("CONNECTIONS_S3_ENDPOINT", "https://fly.storage.tigris.dev")
BUCKET = os.getenv("CONNECTIONS_S3_BUCKET", "rzierke-static-connections")
PREFIX = "connections/"


class Command(BaseCommand):
	help = "List Tigris objects not referenced by any Character (optionally delete them)."

	def add_arguments(self, parser):
		parser.add_argument(
			"--delete",
			action="store_true",
			help="Delete the orphaned objects from the bucket after listing them.",
		)

	def handle(self, *args, **options):
		try:
			import boto3
		except ImportError:
			raise CommandError(
				"boto3 is not installed. Run `uv sync` (it is a dependency)."
			)

		if not (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")):
			raise CommandError(
				"AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are not set. "
				"Add the Tigris keys from `flyctl storage create` to your .env."
			)

		from connections.models import Character

		s3 = boto3.client("s3", endpoint_url=ENDPOINT_URL)

		# Every real object under the connections/ prefix (skip any zero-byte
		# "directory" markers that end in a slash).
		remote_keys = set()
		paginator = s3.get_paginator("list_objects_v2")
		for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
			for obj in page.get("Contents", []):
				key = obj["Key"]
				if key.endswith("/"):
					continue
				remote_keys.add(key)

		# Keys at least one Character points at. photo_path is normalized to a
		# bucket key (connections/<name>.png) on save; rows using absolute URLs
		# or paths don't map to a bucket object, so exclude them.
		referenced = set(
			Character.objects.exclude(photo_path="")
			.exclude(photo_path__startswith="http")
			.exclude(photo_path__startswith="/")
			.values_list("photo_path", flat=True)
		)

		orphans = sorted(remote_keys - referenced)

		if not orphans:
			self.stdout.write(
				self.style.SUCCESS(
					f"No orphaned images. {len(remote_keys)} objects in bucket, "
					f"all referenced by a character."
				)
			)
			return

		self.stdout.write(
			self.style.WARNING(
				f"{len(orphans)} orphaned object(s) in {BUCKET} "
				f"({len(remote_keys)} total, {len(remote_keys) - len(orphans)} referenced):"
			)
		)
		for key in orphans:
			self.stdout.write(f"  {key}")

		if not options["delete"]:
			self.stdout.write("\nRe-run with --delete to remove them from the bucket.")
			return

		# delete_objects takes at most 1000 keys per call.
		deleted = 0
		for i in range(0, len(orphans), 1000):
			batch = orphans[i : i + 1000]
			s3.delete_objects(
				Bucket=BUCKET,
				Delete={"Objects": [{"Key": k} for k in batch]},
			)
			deleted += len(batch)
		self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} orphaned object(s)."))
