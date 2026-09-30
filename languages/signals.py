from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import JobPost
from .tasks import enqueue_job_alerts


@receiver(pre_save, sender=JobPost)
def remember_job_validation_state(sender, instance, raw=False, **kwargs):
    instance._was_validated_before_save = False
    if not raw and instance.pk:
        instance._was_validated_before_save = sender.objects.filter(
            pk=instance.pk,
            is_validated=True,
        ).exists()


@receiver(post_save, sender=JobPost)
def schedule_job_alerts(sender, instance, created, raw=False, **kwargs):
    if raw or instance.is_external or not instance.is_validated:
        return
    if created or not getattr(instance, '_was_validated_before_save', False):
        job_id = instance.pk
        transaction.on_commit(lambda: enqueue_job_alerts.delay(job_id), robust=True)