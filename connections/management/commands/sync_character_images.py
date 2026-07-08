'''
File: sync_character_images.py
Project: rzierke-site
Description: Upload new/changed character portraits from
static/public/connections/ to the Tigris bucket that serves them in
production. Local-only tool (boto3 is a dev dependency); run it after
dropping new PNGs into the folder:

	uv run python manage.py sync_character_images

Credentials come from .env: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
(the keys printed by `flyctl storage create`).
'''

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

ENDPOINT_URL = os.getenv("CONNECTIONS_S3_ENDPOINT", "https://fly.storage.tigris.dev")
BUCKET = os.getenv("CONNECTIONS_S3_BUCKET", "rzierke-static-connections")
PREFIX = "connections/"
CACHE_CONTROL = "public, max-age=31536000"


class Command(BaseCommand):
	help = "Upload new or changed character portraits to the Tigris bucket."

	def add_arguments(self, parser):
		parser.add_argument(
			"--dry-run",
			action="store_true",
			help="Show what would be uploaded without uploading anything.",
		)
		parser.add_argument(
			"--force",
			action="store_true",
			help="Re-upload every local file, even if the bucket copy matches.",
		)

	def handle(self, *args, **options):
		try:
			import boto3
		except ImportError:
			raise CommandError(
				"boto3 is not installed. Run `uv sync` (it is a dev dependency)."
			)

		if not (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")):
			raise CommandError(
				"AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are not set. "
				"Add the Tigris keys from `flyctl storage create` to your .env."
			)

		local_dir = Path(settings.BASE_DIR) / "static" / "public" / "connections"
		if not local_dir.is_dir():
			raise CommandError(f"Local image folder not found: {local_dir}")

		s3 = boto3.client("s3", endpoint_url=ENDPOINT_URL)

		remote_sizes = {}
		paginator = s3.get_paginator("list_objects_v2")
		for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
			for obj in page.get("Contents", []):
				remote_sizes[obj["Key"]] = obj["Size"]

		local_files = sorted(
			p for p in local_dir.iterdir()
			if p.is_file() and p.suffix.lower() == ".png"
		)
		to_upload = []
		for path in local_files:
			key = f"{PREFIX}{path.name}"
			size = path.stat().st_size
			if options["force"] or remote_sizes.get(key) != size:
				to_upload.append((path, key))

		for path, key in to_upload:
			verb = "Would upload" if options["dry_run"] else "Uploading"
			self.stdout.write(f"{verb} {key} ({path.stat().st_size:,} bytes)")
			if not options["dry_run"]:
				s3.upload_file(
					str(path),
					BUCKET,
					key,
					ExtraArgs={
						"ContentType": "image/png",
						"CacheControl": CACHE_CONTROL,
					},
				)

		self.stdout.write(
			self.style.SUCCESS(
				f"{len(to_upload)} uploaded, "
				f"{len(local_files) - len(to_upload)} already up to date, "
				f"{len(remote_sizes)} objects in bucket."
			)
		)

		# Catch typos: characters whose photo_path has no matching object.
		from connections.models import Character

		bucket_keys = set(remote_sizes) | {key for _, key in to_upload}
		missing = (
			Character.objects.exclude(photo_path="")
			.exclude(photo_path__startswith="http")
			.exclude(photo_path__startswith="/")
			.exclude(photo_path__in=bucket_keys)
			.values_list("name", "photo_path")
		)
		for name, photo_path in missing:
			self.stdout.write(
				self.style.WARNING(f"No image in bucket for {name}: {photo_path}")
			)
