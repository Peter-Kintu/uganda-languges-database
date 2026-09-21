from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from users.models import AgentPlan, AgentResearchCitation
import os
import requests


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


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def refresh_agent_plan_research(self, plan_id):
    """Refresh plan citations without blocking the user's chat request."""
    plan = AgentPlan.objects.select_related('user').get(id=plan_id)
    api_key = os.environ.get('BRAVE_SEARCH_API_KEY', '').strip()
    if not api_key:
        return {'plan_id': plan.id, 'sources': 0, 'status': 'search_provider_not_configured'}
    response = requests.get(
        'https://api.search.brave.com/res/v1/web/search',
        headers={'Accept': 'application/json', 'X-Subscription-Token': api_key},
        params={'q': plan.goal[:500], 'count': 5, 'country': 'ug', 'search_lang': 'en'},
        timeout=20,
    )
    response.raise_for_status()
    results = response.json().get('web', {}).get('results', [])
    AgentResearchCitation.objects.filter(plan=plan).delete()
    AgentResearchCitation.objects.bulk_create([
        AgentResearchCitation(
            user=plan.user,
            plan=plan,
            query=plan.goal[:500],
            title=str(item.get('title', 'Untitled'))[:500],
            url=str(item.get('url', ''))[:1000],
            excerpt=str(item.get('description', ''))[:2000],
        )
        for item in results if item.get('url')
    ])
    return {'plan_id': plan.id, 'sources': len(results), 'status': 'complete'}
