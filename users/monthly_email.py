from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from users.models import CustomUser, MonthlyEmailDelivery


def send_monthly_emails(batch_size=None):
    """Send a small idempotent batch to all users with email addresses."""
    month = timezone.localdate().replace(day=1)
    if batch_size is None:
        batch_size = settings.MONTHLY_EMAIL_BATCH_SIZE
    if batch_size < 1:
        raise ValueError('Monthly email batch size must be at least 1.')

    sent_count = 0
    failed_count = 0

    users = CustomUser.objects.filter(
        email__isnull=False,
    ).exclude(
        email='',
    ).annotate(
        already_sent=Exists(
            MonthlyEmailDelivery.objects.filter(
                user_id=OuterRef('pk'),
                month=month,
            )
        )
    ).filter(
        already_sent=False,
    ).only('id', 'username', 'email').order_by('id')[:batch_size]

    for user in users:
        try:
            with transaction.atomic():
                MonthlyEmailDelivery.objects.create(user=user, month=month)
        except IntegrityError:
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
        'failed': failed_count,
        'batch_size': batch_size,
    }
