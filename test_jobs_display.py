#!/usr/bin/env python
"""Manual job-display smoke test. Run directly, never during test discovery."""
import os


def main():
    import django

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
    django.setup()

    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory
    from languages.views import browse_job_listings, deduplicate_jobs, fetch_jooble_data

    jooble_jobs = fetch_jooble_data('python', '')
    print(f'Jooble returned {len(jooble_jobs)} jobs')
    print(f'After dedup: {len(deduplicate_jobs(jooble_jobs))} jobs')

    request = RequestFactory().get('/jobs/')
    request.user = AnonymousUser()
    response = browse_job_listings(request)
    if hasattr(response, 'render'):
        response.render()
    print(f'Browse view executed successfully: {type(response).__name__}')


if __name__ == '__main__':
    main()
