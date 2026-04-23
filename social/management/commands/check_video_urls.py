from django.core.management.base import BaseCommand
from social.models import BusinessReel

class Command(BaseCommand):
    help = 'Check all video URLs in the database'

    def handle(self, *args, **options):
        reels = BusinessReel.objects.all()
        
        if not reels.exists():
            self.stdout.write(self.style.WARNING('No reels found in database'))
            return
        
        self.stdout.write(f'Found {reels.count()} reels\n')
        
        for reel in reels:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(f'Reel ID: {reel.id}')
            self.stdout.write(f'Author: {reel.author.username}')
            self.stdout.write(f'Caption: {reel.caption[:50]}...')
            self.stdout.write(f'Video field value: {reel.video}')
            self.stdout.write(f'Video URL: {reel.video.url}')
            self.stdout.write(f'Video path: {reel.video.path if hasattr(reel.video, "path") else "N/A"}')
            self.stdout.write(f'Active: {reel.is_active}')
            self.stdout.write(f'Created: {reel.created_at}')
            
            # Check if file exists
            try:
                if hasattr(reel.video, 'storage'):
                    exists = reel.video.storage.exists(reel.video.name)
                    self.stdout.write(f'File exists: {exists}')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Could not check file existence: {e}'))
