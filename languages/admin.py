from django.contrib import admin
from .models import PhraseContribution
from django.http import JsonResponse
import json

# Define a custom action for the admin panel
def export_as_json(modeladmin, request, queryset):
    """
    Admin action to export selected contributions as a JSON file.
    """
    data = list(queryset.values('text', 'translation', 'language', 'intent'))
    response = JsonResponse(data, safe=False)
    response['Content-Disposition'] = 'attachment; filename="selected_contributions.json"'
    return response

# Give the action a human-friendly name
export_as_json.short_description = "Export selected contributions as JSON"

# A custom admin class for the PhraseContribution model.
# This enhances the admin interface to make it easier to manage contributions.
@admin.register(PhraseContribution)
class PhraseContributionAdmin(admin.ModelAdmin):
    # This defines the fields that will be displayed in the list view.
    list_display = (
        'text', 
        'translation', 
        'language', 
        'intent', 
        'contributor_name', 
        'timestamp', 
        'is_validated'
    )
    
    # These fields can be used for filtering the contributions.
    list_filter = ('language', 'intent', 'is_validated')
    
    # This enables a search bar to search through the specified fields.
    search_fields = ('text', 'translation', 'contributor_name')
    
    # This allows for bulk actions on selected contributions.
    actions = ['mark_validated', export_as_json]

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
