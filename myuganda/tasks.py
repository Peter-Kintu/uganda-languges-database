from celery import shared_task


@shared_task(bind=True)
def debug_celery_task(self):
    print('Celery is working correctly.')
    return {'status': 'ok'}
