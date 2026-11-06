from django.core.management.base import BaseCommand

from users.monthly_email import send_monthly_emails


class Command(BaseCommand):
    help = 'Send a small idempotent monthly update batch to users with email addresses.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=None,
            help='Maximum number of users to email during this run.',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        if batch_size is not None and batch_size < 1:
            self.stderr.write(self.style.ERROR('--batch-size must be at least 1.'))
            return

        result = send_monthly_emails(batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(
                'Monthly email batch complete: '
                f"{result['sent']} sent, {result['failed']} failed, "
                f"batch limit {result['batch_size']}."
            )
        )
