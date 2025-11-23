from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

# Renamed LANGUAGES to JOB_CATEGORIES
JOB_CATEGORIES = (
     # IT/Tech Jobs (Original Bantu Languages)
    ('luganda', 'Information Technology'),
    ('lusoga', 'Software Development'),
    ('lugwere', 'Data Science & AI'),
    ('lumasaba', 'Cyber Security'),
    ('samia', 'Cloud Engineering'),
    # Business/Finance Jobs (Original Nilotic Languages)
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
    # Remaining original languages...
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
    
    class Meta:
        verbose_name = _("Recruiter")
        verbose_name_plural = _("Recruiters")

    def __str__(self):
        return self.recruiter_name

    def calculate_total_posts(self):
        return self.jobpost_set.count()

    def get_monthly_posts(self, month, year):
        return self.jobpost_set.filter(timestamp__year=year, timestamp__month=month).count()


# Renamed PhraseContribution to JobPost
class JobPost(models.Model):
    """
    Represents a single job post (was: language phrase/sentence).
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
    
    # Renamed 'text' to 'post_content'
    post_content = models.TextField(
        help_text=_("The full description of the job.")
    )
    
    # Renamed 'translation' to 'required_skills'
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
    
    # Renamed contributor fields
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

    timestamp = models.DateTimeField(auto_now_add=True)
    is_validated = models.BooleanField(
        default=False, 
        help_text=_("Marks if the job post has been reviewed and validated.")
    )
    # Renamed 'likes' to 'upvotes'
    upvotes = models.IntegerField(default=0)

    # === NEW FIELD FOR FILE UPLOAD ===
    company_logo_or_media = models.FileField(
        upload_to='job_media/', 
        null=True,                       
        blank=True,                      
        help_text=_("Optional: Upload a company logo (image) or short recruitment video.")
    )

    # === NEW FIELD FOR APPLICATION LINK ===
    application_url = models.URLField(
        max_length=200, 
        null=True, 
        blank=True,
        help_text=_("The direct link where applicants can apply for this job (e.g., Company career page, LinkedIn, or email).")
    )

    class Meta:
        verbose_name = _("Job Post")
        verbose_name_plural = _("Job Posts")
        ordering = ['-timestamp']

    def __str__(self):
        # Displays the first 30 characters of the post content
        return f"{self.job_category} - {self.post_content[:30]}..."