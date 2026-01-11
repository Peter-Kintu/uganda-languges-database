from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

# Renamed LANGUAGES to JOB_CATEGORIES
JOB_CATEGORIES = (
    # IT/Tech Jobs (Original Bantu Languages mapping)
    ('luganda', 'Information Technology'),
    ('lusoga', 'Software Development'),
    ('lugwere', 'Data Science & AI'),
    ('lumasaba', 'Cyber Security'),
    ('samia', 'Cloud Engineering'),
    # Business/Finance Jobs (Original Nilotic Languages mapping)
    ('runyankole', 'Finance & Accounting'),
    ('rukiga', 'Marketing & Sales'),
    ('runyoro', 'Human Resources'),
    ('rutooro', 'Supply Chain & Logistics'),
    ('runyakitara', 'Project Management'),
    # Creative/Other Jobs
    ('kinyarwanda', 'Creative Design'),
    ('acholi', 'Customer Support'),
    ('alur', 'Healthcare & Pharma'),
    ('ateso', 'Education & Training'),
    ('sw', 'General Management'),
    # Remaining categories...
    ('chope', 'Manufacturing'),
    ('lukenye', 'Telecommunications'),
    ('lussese', 'Real Estate'),
    ('langi', 'Government/Public Sector'),
    ('kupsapiiny', 'Energy & Utilities'),
    ('sabiny', 'Legal Services'),
    ('sebei', 'Agriculture'),
    ('suam', 'NGO/Non-Profit'),
    ('pokot', 'Hospitality/Travel'),
)

# Renamed INTENTS to JOB_TYPES
JOB_TYPES = (
    ('fulltime', 'Full-Time'),
    ('parttime', 'Part-Time'),
    ('contract', 'Contract'),
    ('internship', 'Internship'),
    ('freelance', 'Freelance'),
)


# New model for recruiters (was: Contributor)
class Applicant(models.Model):
    """
    Represents a recruiter/company that posts jobs.
    Tracks their total contributions to rank them.
    """
    recruiter_name = models.CharField(max_length=100, unique=True)
    total_posts = models.IntegerField(default=0)
    location = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = _("Recruiter")
        verbose_name_plural = _("Recruiters")

    def __str__(self):
        return self.recruiter_name

    def calculate_total_posts(self):
        """Recalculates total posts based on related JobPost count."""
        count = self.jobpost_set.count()
        self.total_posts = count
        self.save(update_fields=["total_posts"])
        return count

    def get_monthly_posts(self, month, year):
        return self.jobpost_set.filter(timestamp__year=year, timestamp__month=month).count()


# Renamed PhraseContribution to JobPost
class JobPost(models.Model):
    """
    Represents a single job post.
    Supports local entries and external API backfilling.
    """
    job_category = models.CharField(
        max_length=20,
        choices=JOB_CATEGORIES,
        default='luganda',
        help_text=_("Select the industry/category for this job.")
    )
    job_type = models.CharField(
        max_length=20,
        choices=JOB_TYPES,
        default='fulltime',
        help_text=_("Select the type of employment.")
    )

    post_content = models.TextField(
        help_text=_("The full description of the job.")
    )

    required_skills = models.TextField(
        help_text=_("List the essential skills and qualifications.")
    )

    # ForeignKey to the Applicant (Recruiter) model
    applicant = models.ForeignKey(
        Applicant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("The Applicant (Recruiter) associated with this job post.")
    )

    recruiter_name = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("The name of the recruiter/posting company.")
    )
    recruiter_location = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("The location of the company/recruiter.")
    )

    # === EASY APPLY CONTACT FIELDS ===
    recruiter_email = models.EmailField(
        max_length=254,
        null=True,
        blank=True,
        help_text=_("The email address applicants should use for 'Easy Apply'.")
    )
    recruiter_whatsapp = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text=_("The WhatsApp number (e.g., +256701234567) applicants should use for 'Easy Apply'.")
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    is_validated = models.BooleanField(
        default=True,
        help_text=_("Marks if the job post has been reviewed and validated.")
    )
    upvotes = models.IntegerField(default=0)

    # === FILE UPLOAD ===
    company_logo_or_media = models.FileField(
        upload_to='job_media/',
        null=True,
        blank=True,
        help_text=_("Optional: Upload a company logo (image) or short recruitment video.")
    )

    # === APPLICATION LINK (NON-EASY APPLY) ===
    application_url = models.URLField(
        max_length=1000,
        null=True,
        blank=True,
        help_text=_("The direct link where applicants can apply for this job.")
    )

    # === WATERFALL & PPC STRATEGY FIELDS ===
    is_external = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("True if this job is backfilled from an external partner API (e.g., Adzuna).")
    )
    external_source = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("The name of the partner (e.g., Adzuna, Careerjet).")
    )
    click_count = models.PositiveIntegerField(
        default=0,
        help_text=_("Tracks outbound clicks to monitor PPC revenue performance.")
    )

    class Meta:
        verbose_name = _("Job Post")
        verbose_name_plural = _("Job Posts")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['is_external', 'job_category']),
        ]

    def __str__(self):
        return f"{self.job_category} - {self.post_content[:30]}..."

    def save(self, *args, **kwargs):
        """
        Custom save method to automatically link recruiters, 
        sync location data, and update post counts.
        """
        # Automatically link to an Applicant model if the recruiter_name matches
        if not self.applicant and self.recruiter_name:
            # FIX: Ensure recruiter_location is synced to the Applicant model
            recruiter, created = Applicant.objects.get_or_create(
                recruiter_name=self.recruiter_name,
                defaults={'location': self.recruiter_location}
            )
            self.applicant = recruiter
        
        # Fallback if applicant exists but location is missing on the profile
        if self.applicant and not self.applicant.location and self.recruiter_location:
            self.applicant.location = self.recruiter_location
            self.applicant.save(update_fields=['location'])

        super().save(*args, **kwargs)

        # Update the total_posts count for the linked recruiter
        if self.applicant:
            self.applicant.calculate_total_posts()