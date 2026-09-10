from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_user_notification_task(self, user_email, subject, message):
    """Send one user notification through the configured email backend."""
    if not user_email:
        return False

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
        fail_silently=False,
    )
    return True
