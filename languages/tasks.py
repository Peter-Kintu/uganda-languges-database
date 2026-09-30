from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import JobAlert, JobAlertDelivery, JobPost


def job_is_alertable(job):
    return (
        not job.is_external
        and job.is_validated
        and (job.valid_through is None or job.valid_through > timezone.now())
    )


def alert_matches_job(alert, job):
    if alert.category and alert.category != job.job_category:
        return False

    if alert.role_query:
        searchable_text = ' '.join((job.post_content, job.required_skills, job.recruiter_name)).casefold()
        if alert.role_query.casefold() not in searchable_text:
            return False

    if alert.location:
        searchable_location = ' '.join((job.recruiter_location, job.job_location_address)).casefold()
        if alert.location.casefold() not in searchable_location:
            return False

    return True


@shared_task
def enqueue_job_alerts(job_id):
    job = JobPost.objects.filter(pk=job_id).first()
    if not job or not job_is_alertable(job):
        return 0

    queued = 0
    alerts = JobAlert.objects.select_related('user').filter(is_active=True).iterator()
    for alert in alerts:
        if alert.user.email and alert_matches_job(alert, job):
            send_job_alert_email.delay(alert.pk, job.pk)
            queued += 1
    return queued


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_job_alert_email(self, alert_id, job_id):
    alert = JobAlert.objects.select_related('user').filter(pk=alert_id, is_active=True).first()
    job = JobPost.objects.filter(pk=job_id).first()
    if not alert or not job or not alert.user.email or not job_is_alertable(job):
        return False
    if not alert_matches_job(alert, job):
        return False

    delivery, _created = JobAlertDelivery.objects.get_or_create(alert=alert, job=job)
    if delivery.sent_at:
        return True

    domain = settings.DEFAULT_DOMAIN.strip().strip('/')
    job_url = f"https://{domain}{reverse('languages:job_post_detail', args=[job.pk])}"
    alerts_url = f"https://{domain}{reverse('languages:job_alerts')}"
    subject = f"New job matching your alert: {job.recruiter_name or 'Job opportunity'}"
    message = (
        f"A new local job matches your saved alert.\n\n"
        f"{job.post_content[:500]}\n\n"
        f"Location: {job.recruiter_location or job.job_location_address or 'Not specified'}\n"
        f"View the job: {job_url}\n\n"
        f"Manage or pause your alerts: {alerts_url}\n"
    )
    sent_count = send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [alert.user.email],
        fail_silently=False,
    )
    if sent_count:
        delivery.sent_at = timezone.now()
        delivery.save(update_fields=['sent_at'])
    return bool(sent_count)