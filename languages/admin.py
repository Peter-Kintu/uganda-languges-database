# File: languages/admin.py

from django.contrib import admin
from .models import JobPost, Applicant # Updated model names
from django.urls import reverse
from django.shortcuts import redirect


admin.site.register(Applicant) # Updated model name
# A custom admin class for the JobPost model.
class JobPostAdmin(admin.ModelAdmin):
    # This defines the fields that will be displayed in the list view.
    list_display = (
        'post_content', 
        'required_skills', 
        'job_category', 
        'job_type', 
        'recruiter_name',
        'application_url', # <--- NEW FIELD
        'company_logo_or_media', # <--- ADDED FIELD
        'upvotes', # Updated field name
        'applicant',  # Updated field name
        'timestamp', 
        'is_validated'
    )
    
    # These fields can be used for filtering the posts.
    list_filter = ('job_category', 'job_type', 'is_validated')
    
    # This enables a search bar to search through the specified fields.
    search_fields = ('post_content', 'required_skills', 'recruiter_name')
    
    # This allows for bulk actions on selected job posts.
    actions = ['mark_validated', 'export_json', 'reset_upvotes'] # Updated action name

    # Custom action to mark selected posts as validated.
    @admin.action(description='Mark selected job posts as validated') 
    def mark_validated(self, request, queryset):
        # Update the 'is_validated' field to True for the selected items.
        updated_count = queryset.update(is_validated=True)
        self.message_user(
            request, 
            f'{updated_count} job post(s) were successfully marked as validated.'
        )

    # Custom action to reset upvotes
    @admin.action(description='Reset upvotes for selected job posts')
    def reset_upvotes(self, request, queryset): # Renamed function
        # Update the 'upvotes' field to 0 for the selected items.
        updated_count = queryset.update(upvotes=0) # Updated field name
        self.message_user(
            request,
            f'Upvotes were reset for {updated_count} job post(s).'
        )
    
    # Custom action to export validated job posts as JSON.
    @admin.action(description='Export validated job posts as JSON')
    def export_json(self, request, queryset):
        # Redirect to the export view (URL name remains 'export_json' for simplicity)
        return redirect('export_contributions_json')
    
# Register the model with the custom admin class.
admin.site.register(JobPost, JobPostAdmin)