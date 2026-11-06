from django.core.management.base import BaseCommand

from users.monthly_email import send_monthly_emails


class Command(BaseCommand):
    help = 'Send one idempotent monthly update email to every active user with an email.'

    def handle(self, *args, **options):
        result = send_monthly_emails()
        self.stdout.write(
            self.style.SUCCESS(
                'Monthly email complete: '
                f"{result['sent']} sent, {result['skipped']} already sent, "
                f"{result['failed']} failed."
            )
        )
