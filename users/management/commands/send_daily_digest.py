from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings


User = get_user_model()


class Command(BaseCommand):
    help = 'Send a daily update email to active users with email addresses.'

    def handle(self, *args, **options):
        sent_count = 0
        failed_count = 0
        active_users = User.objects.filter(is_active=True).exclude(email='').only('username', 'email')

        for user in active_users.iterator():
            try:
                send_mail(
                    subject='Your Daily Update from Africana AI',
                    message=(
                        f'Hi {user.username},\n\n'
                        'Check out the latest features and activity on Africana AI today!\n\n'
                        'Visit https://www.africanaai.info to get started.\n\n'
                        'The Africana AI team'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception as exc:
                failed_count += 1
                self.stderr.write(f'Failed to send to {user.email}: {exc}')
            else:
                sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Daily digest complete: {sent_count} sent, {failed_count} failed.'
            )
        )
