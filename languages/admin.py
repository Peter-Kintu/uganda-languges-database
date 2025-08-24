# File: languages/admin.py

from django.contrib import admin
from .models import PhraseContribution
from django.urls import reverse
from django.shortcuts import redirect
from .models import PhraseContribution, Contributor



admin.site.register(Contributor)
# A custom admin class for the PhraseContribution model.
# This enhances the admin interface to make it easier to manage contributions.
class PhraseContributionAdmin(admin.ModelAdmin):
    # This defines the fields that will be displayed in the list view.
    list_display = (
        'text', 
        'translation', 
        'language', 
        'intent', 
        'contributor_name',
        'likes',
        'contributor',  
        'timestamp', 
        'is_validated'
    )
    
    # These fields can be used for filtering the contributions.
    list_filter = ('language', 'intent', 'is_validated')
    
    # This enables a search bar to search through the specified fields.
    search_fields = ('text', 'translation', 'contributor_name')
    
    # This allows for bulk actions on selected contributions.
    # We add our new export action here.
    actions = ['mark_validated', 'export_json']

    # Custom action to mark selected contributions as validated.
    # The short_description is what will appear in the action dropdown.
    @admin.action(description='Mark selected contributions as validated')
    def mark_validated(self, request, queryset):
        # Update the 'is_validated' field to True for the selected items.
        updated_count = queryset.update(is_validated=True)
        self.message_user(
            request, 
            f'{updated_count} contribution(s) were successfully marked as validated.'
        )

    @admin.action(description='Reset likes for selected contributions')
    def reset_likes(self, request, queryset):
        # Update the 'likes' field to 0 for the selected items.
        updated_count = queryset.update(likes=0)
        self.message_user(
            request,
            f'Likes were reset for {updated_count} contribution(s).'
        )
    

    # Custom action to export validated contributions as JSON.
    @admin.action(description='Export validated contributions as JSON')
    def export_json(self, request, queryset):
        # We don't need the queryset for this action, as the view will handle it.
        # We just need to redirect to our new view.
        return redirect('export_contributions_json')
    
# Register the model with the custom admin class.
admin.site.register(PhraseContribution, PhraseContributionAdmin)
