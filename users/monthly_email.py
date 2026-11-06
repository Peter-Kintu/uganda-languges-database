from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from users.models import CustomUser, MonthlyEmailDelivery


def send_monthly_emails():
    """Send one idempotent Africana AI update to every active user with an email."""
    month = timezone.localdate().replace(day=1)
    sent_count = 0
    skipped_count = 0
    failed_count = 0

    users = CustomUser.objects.filter(
        is_active=True,
    ).exclude(email='').only('id', 'username', 'email')

    for user in users.iterator():
        try:
            with transaction.atomic():
                MonthlyEmailDelivery.objects.create(user=user, month=month)
        except IntegrityError:
            skipped_count += 1
            continue

        try:
            send_mail(
                subject='Your monthly update from Africana AI',
                message=(
                    f'Hi {user.get_full_name() or user.username},\n\n'
                    'Here is your monthly reminder from Africana AI: explore new '
                    'jobs, connect with African professionals, and discover tools '
                    'that help you build and grow.\n\n'
                    'Visit https://www.africanaai.info to get started.\n\n'
                    'The Africana AI team'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            MonthlyEmailDelivery.objects.filter(user=user, month=month).delete()
            failed_count += 1
        else:
            sent_count += 1

    return {
        'month': month.isoformat(),
        'sent': sent_count,
        'skipped': skipped_count,
        'failed': failed_count,
    }
