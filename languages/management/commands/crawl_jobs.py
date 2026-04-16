from django.core.management.base import BaseCommand
from languages.models import JobPost

try:
    from jobspy import scrape_jobs
except ImportError:
    scrape_jobs = None


class Command(BaseCommand):
    help = '''
    Crawl global job boards using python-jobspy and cache results locally.
    
    RECOMMENDED USAGE & BEST PRACTICES:
    
    1. Manual Testing:
        python manage.py crawl_jobs "python developer" --location="Uganda" --results=10 --hours=72
    
    2. Automated via Cron (every 6 hours):
        0 */6 * * * cd /path/to/project && python manage.py crawl_jobs "software engineer" --location="Uganda" --results=20
    
    3. Production Considerations:
        - Start with --results=5 or --results=10 to avoid timeouts
        - Use a cron job or Celery Beat for scheduled crawls (not on every user request)
        - LinkedIn and Indeed may rate-limit/block after heavy usage; rotate proxies if needed
        - Results are deduplicated by application_url to avoid database bloat
        - Use --hours to filter for fresh jobs only
    
    OUTPUT:
        - Creates new JobPost entries with is_external=True, external_source='jobspy'
        - Cached results appear in "Global Internet Jobs" search mode
        - Results can be paginated and searched like local jobs
    '''

    def add_arguments(self, parser):
        parser.add_argument('query', type=str, help='Job title or search phrase to crawl for.')
        parser.add_argument('--location', type=str, default='Uganda', help='Location to search for.')
        parser.add_argument('--results', type=int, default=10, help='Number of jobs to request per site (default 10).')
        parser.add_argument('--hours', type=int, default=72, help='Only include listings published in the last X hours.')

    def handle(self, *args, **options):
        if scrape_jobs is None:
            self.stderr.write(self.style.ERROR(
                'python-jobspy is not installed. Install with: pip install python-jobspy'
            ))
            return

        query = options['query']
        location = options['location']
        results_wanted = options['results']
        hours_old = options['hours']

        self.stdout.write(self.style.NOTICE(f'Starting crawl for "{query}" in {location}...'))
        self.stdout.write(f'Targeting ~{results_wanted} results per site, refreshing every {hours_old} hours.')

        try:
            jobs = scrape_jobs(
                site_name=["indeed", "linkedin", "zip_recruiter", "glassdoor"],
                search_term=query,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
            )
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Crawler failed: {exc}'))
            self.stderr.write('Note: If you see rate-limit errors, reduce --results or add proxies to jobspy.')
            return

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for row in jobs.iterrows():
            index, data = row
            job_url = data.get('job_url') or data.get('url') or data.get('job_link')
            title = data.get('title') or data.get('description') or query
            description = data.get('description') or title
            company = data.get('company') or 'Global Employer'
            job_location = data.get('location') or location or 'Remote'

            if not job_url:
                skipped_count += 1
                continue

            defaults = {
                'post_content': description,
                'required_skills': data.get('description') or title,
                'recruiter_name': company,
                'recruiter_location': job_location,
                'application_url': job_url,
                'is_external': True,
                'external_source': 'jobspy',
                'job_type': 'fulltime',
                'job_category': 'luganda',
            }

            job_post, created = JobPost.objects.get_or_create(
                application_url=job_url,
                defaults=defaults,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
                for field, value in defaults.items():
                    setattr(job_post, field, value)
                job_post.save()

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Crawl complete for "{query}"'
        ))
        self.stdout.write(f'  Created: {created_count} new jobs')
        self.stdout.write(f'  Updated: {updated_count} existing jobs')
        self.stdout.write(f'  Skipped: {skipped_count} (missing URL)')
        self.stdout.write(f'\nResults now available in "Global Internet Jobs" search mode.')

