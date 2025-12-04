from django import forms
from .models import JobPost # Updated import to the new model name

# Renamed PhraseContributionForm to JobPostForm
class JobPostForm(forms.ModelForm):
    """
    A form for users (recruiters) to submit new job posts (language data).
    """
    class Meta:
        # Specifies the model this form is based on.
        model = JobPost
        
        # Defines which fields from the model should be included in the form.
        fields = [
            'job_category', 
            'job_type', 
            'post_content', 
            'required_skills', 
            'recruiter_name', 
            'recruiter_location',
            'application_url', 
            'recruiter_email',       # <--- ADDED FIELD
            'recruiter_whatsapp',    # <--- ADDED FIELD
            'company_logo_or_media', 
        ]
        
        # Customizes the HTML widgets with job-themed placeholders.
        widgets = {
            # This is the original 'text' field (the phrase/sentence)
            'post_content': forms.Textarea(attrs={
                'rows': 4, 
                'placeholder': 'Enter the full job description here...',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
            # This is the original 'translation' field (the translation)
            'required_skills': forms.Textarea(attrs={
                'rows': 4, 
                'placeholder': 'List essential skills, e.g., Python, Django, Tailwind CSS, 3+ years experience...',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
            # This is the original 'contributor_name' field
            'recruiter_name': forms.TextInput(attrs={
                'placeholder': 'Your Name or Company Name (required)',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
            # This is the original 'contributor_location' field
            'recruiter_location': forms.TextInput(attrs={
                'placeholder': 'Company Headquarters or Remote Location',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
            # ADDED: Widget for the new application URL field
            'application_url': forms.URLInput(attrs={
                'placeholder': 'https://company.com/apply/job-title (Alternative to Easy Apply)',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
            # NEW: Widget for Recruiter Email
            'recruiter_email': forms.EmailInput(attrs={
                'placeholder': 'application@company.com (For Easy Apply applicants)',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
            # NEW: Widget for Recruiter WhatsApp
            'recruiter_whatsapp': forms.TextInput(attrs={
                'placeholder': '+256770123456 (For Easy Apply applicants, no spaces/dashes)',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
            # ADDED: Widget for the new file field. Using a standard file input class.
            'company_logo_or_media': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm text-gray-300 border border-gray-700 rounded-lg cursor-pointer bg-gray-800 focus:outline-none focus:border-indigo-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-700'
            }),
        }
        
        # Provides custom, more user-friendly labels for the fields.
        labels = {
            'post_content': 'Job Description',
            'required_skills': 'Required Skills/Qualifications',
            'job_category': 'Job Industry/Category',
            'job_type': 'Employment Type',
            'recruiter_name': 'Your/Company Name',
            'recruiter_location': 'Location',
            'application_url': 'External Application Link (URL)', 
            'recruiter_email': 'Easy Apply Email',       # <--- ADDED LABEL
            'recruiter_whatsapp': 'Easy Apply WhatsApp Number', # <--- ADDED LABEL
            'company_logo_or_media': 'Company Logo or Media',
        }
        
        # Excludes the 'applicant' field, which is handled in the view.
        exclude = ('applicant',)