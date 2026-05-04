"""
Django Management Command: Sync YouTube videos for all active partnerships.
Usage: python manage.py sync_youtube_videos
Schedule this with Celery Beat or APScheduler for periodic execution.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from social.models import YouTubeChannel, YouTubePartnership
from social.youtube_service import YouTubeSyncService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync YouTube videos for all active partnerships and channels'

    def add_arguments(self, parser):
        parser.add_argument(
            '--channel-id',
            type=int,
            help='Sync a specific channel by ID',
        )
        parser.add_argument(
            '--partner-id',
            type=int,
            help='Sync all channels for a specific partner user ID',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if sync frequency hasn\'t elapsed',
        )

    def handle(self, *args, **options):
        try:
            sync_service = YouTubeSyncService()
            
            if options['channel_id']:
                # Sync specific channel
                self._sync_channel(sync_service, options['channel_id'], options['force'])
            elif options['partner_id']:
                # Sync all channels for a partner
                self._sync_partner(sync_service, options['partner_id'], options['force'])
            else:
                # Sync all active channels
                self._sync_all(sync_service, options['force'])
        
        except Exception as e:
            logger.error(f"Sync error: {str(e)}")
            raise CommandError(f"Sync failed: {str(e)}")

    def _sync_channel(self, sync_service, channel_id, force=False):
        """Sync a specific channel."""
        try:
            channel = YouTubeChannel.objects.get(id=channel_id)
            
            if not force and channel.last_synced_at:
                from datetime import timedelta
                next_sync = channel.last_synced_at + timedelta(hours=channel.sync_frequency_hours)
                if timezone.now() < next_sync:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Channel {channel.channel_name} not ready for sync yet. "
                            f"Next sync at: {next_sync}"
                        )
                    )
                    return
            
            result = sync_service.sync_channel_videos(channel)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Synced {channel.channel_name}: "
                    f"{result['synced']} new videos, {result['skipped']} skipped"
                )
            )
            
            if result['errors']:
                for error in result['errors']:
                    self.stdout.write(self.style.ERROR(f"  ⚠️ {error}"))
        
        except YouTubeChannel.DoesNotExist:
            raise CommandError(f"Channel with ID {channel_id} not found")

    def _sync_partner(self, sync_service, partner_id, force=False):
        """Sync all channels for a specific partner."""
        try:
            partnership = YouTubePartnership.objects.get(user__id=partner_id)
            channels = partnership.channels.filter(is_syncing=True)
            
            total_synced = 0
            for channel in channels:
                if not force and channel.last_synced_at:
                    from datetime import timedelta
                    next_sync = channel.last_synced_at + timedelta(hours=channel.sync_frequency_hours)
                    if timezone.now() < next_sync:
                        continue
                
                result = sync_service.sync_channel_videos(channel)
                total_synced += result['synced']
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Partner {partnership.user.username}: {total_synced} videos synced"
                )
            )
        
        except YouTubePartnership.DoesNotExist:
            raise CommandError(f"Partnership for user ID {partner_id} not found")

    def _sync_all(self, sync_service, force=False):
        """Sync all active channels."""
        stats = sync_service.sync_all_active_channels()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Sync complete! "
                f"{stats['total_synced']} videos synced across "
                f"{stats['channels_processed']} channels"
            )
        )
        
        if stats['errors']:
            self.stdout.write(self.style.ERROR("Errors encountered:"))
            for error in stats['errors']:
                self.stdout.write(self.style.ERROR(f"  ⚠️ {error}"))
