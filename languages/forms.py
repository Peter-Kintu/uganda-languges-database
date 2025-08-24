from django import forms
from .models import PhraseContribution

class PhraseContributionForm(forms.ModelForm):
    """
    A form for users to submit new phrase contributions to the database.
    It uses a ModelForm to automatically create form fields based on the
    PhraseContribution model, and then customizes them for better user experience.
    """
    class Meta:
        # Specifies the model this form is based on.
        model = PhraseContribution
        
        # Defines which fields from the model should be included in the form.
        fields = [
            'language', 
            'intent', 
            'text', 
            'translation', 
            'contributor_name', 
            'contributor_location'
        ]
        
        # Customizes the HTML widgets for each field to add attributes like
        # placeholders, rows for textareas, and CSS classes for styling.
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 4, 
                'placeholder': 'Enter a word, phrase, or sentence...',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
            'translation': forms.Textarea(attrs={
                'rows': 4, 
                'placeholder': 'Optional: Enter the English translation...',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
            'contributor_name': forms.TextInput(attrs={
                'placeholder': 'Optional: Your name',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
            'contributor_location': forms.TextInput(attrs={
                'placeholder': 'Optional: Your community or location',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
        }
        
        # Provides custom, more user-friendly labels for the fields.
        labels = {
            'text': 'Contribution (Word/Phrase/Sentence)',
            'translation': 'English Translation',
            'contributor_name': 'Your Name',
            'contributor_location': 'Your Community/Location',
        }

