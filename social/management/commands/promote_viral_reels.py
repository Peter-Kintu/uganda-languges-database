"""
Management Command: Promote Viral Reels to Cloudinary
Purpose: Automatically migrate high-engagement videos from local server disk to Cloudinary CDN.

Usage:
    python manage.py promote_viral_reels                    # Default: 50 views threshold
    python manage.py promote_viral_reels --threshold 100    # Custom threshold
    python manage.py promote_viral_reels --dry-run          # Preview changes without executing

This implements Tier 3 migration (LOCAL → CLOUDINARY) for sustainable platform growth.
Runs as:
    - Manual command
    - Scheduled cron job (e.g., daily via celery-beat or system cron)
"""

import os
import sys
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import F
from social.models import BusinessReel

try:
    import cloudinary
    import cloudinary.uploader
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False


class Command(BaseCommand):
    help = "Promote viral reels from local storage to Cloudinary CDN based on views threshold."

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=int,
            default=50,
            help='Minimum views required to promote a video (default: 50).'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without executing (test mode).'
        )

    def handle(self, *args, **options):
        threshold = options.get('threshold', 50)
        dry_run = options.get('dry_run', False)

        # Verify Cloudinary is configured
        if not CLOUDINARY_AVAILABLE:
            raise CommandError(
                "cloudinary package not installed. "
                "Run: pip install cloudinary"
            )

        if not hasattr(settings, 'CLOUDINARY_STORAGE'):
            raise CommandError(
                "CLOUDINARY_STORAGE not configured in settings.py. "
                "Set up Cloudinary credentials first."
            )

        # Find LOCAL reels that have exceeded the views threshold
        viral_reels = BusinessReel.objects.filter(
            storage_tier='LOCAL',
            views_count__gte=threshold,
            local_video__isnull=False
        ).exclude(local_video='')

        if not viral_reels.exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ No reels found with {threshold}+ views. Platform is healthy!'
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f'🔍 Found {viral_reels.count()} reel(s) eligible for CDN promotion...'
            )
        )

        promoted_count = 0
        failed_reels = []

        for reel in viral_reels:
            try:
                self.stdout.write(
                    f'\n📹 Processing: "{reel.caption[:50]}" '
                    f'({reel.views_count} views, {reel.author.username})'
                )

                # Skip if already promoted
                if reel.storage_tier == 'CLOUDINARY' and reel.cloudinary_public_id:
                    self.stdout.write(
                        self.style.WARNING(
                            '  ⚠️  Already on Cloudinary CDN. Skipping.'
                        )
                    )
                    continue

                # Get local file path
                local_path = reel.local_video.path
                if not os.path.exists(local_path):
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ❌ Local file missing: {local_path}'
                        )
                    )
                    failed_reels.append(reel.id)
                    continue

                if dry_run:
                    file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✅ [DRY-RUN] Would upload {file_size_mb:.1f}MB to Cloudinary'
                        )
                    )
                    promoted_count += 1
                    continue

                # Upload to Cloudinary
                file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
                self.stdout.write(f'  📤 Uploading {file_size_mb:.1f}MB to Cloudinary...')

                result = cloudinary.uploader.upload_video(
                    local_path,
                    folder='viral_reels_production/',
                    resource_type='video',
                    public_id=f"reel_{reel.id}_{reel.share_token}",
                    overwrite=False,
                    invalidate=True  # Invalidate CDN cache if re-uploading
                )

                # Update reel with Cloudinary public ID
                reel.cloudinary_public_id = result['public_id']
                reel.storage_tier = 'CLOUDINARY'
                reel.save(update_fields=['cloudinary_public_id', 'storage_tier'])

                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✅ Promoted to CDN: {result["secure_url"]}'
                    )
                )

                # Clean up local file
                try:
                    reel.local_video.delete(save=False)  # Delete FileField
                    if os.path.exists(local_path):
                        os.remove(local_path)  # Delete physical file if it still exists
                    self.stdout.write('  🗑️  Cleaned up local storage')
                except Exception as cleanup_error:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  Cleanup error (non-critical): {cleanup_error}'
                        )
                    )

                promoted_count += 1

            except Exception as error:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error: {str(error)}')
                )
                failed_reels.append(reel.id)

        # Summary Report
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS(f'✅ PROMOTION SUMMARY'))
        self.stdout.write('='*70)
        self.stdout.write(f'Promoted to CDN: {promoted_count} reel(s)')
        if failed_reels:
            self.stdout.write(
                self.style.ERROR(f'Failed: {len(failed_reels)} reel(s) (IDs: {failed_reels})')
            )
        self.stdout.write(f'Threshold: {threshold} views')
        if dry_run:
            self.stdout.write(self.style.WARNING('Mode: DRY-RUN (no changes applied)'))
        self.stdout.write('='*70)
