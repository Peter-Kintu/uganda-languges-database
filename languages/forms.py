from django import forms
from .models import PhraseContribution

class PhraseContributionForm(forms.ModelForm):
    """
    A form for users to submit new phrase contributions.
    """
    class Meta:
        model = PhraseContribution
        fields = [
            'language', 
            'intent', 
            'text', 
            'translation', 
            'contributor_name', 
            'contributor_location'
        ]
        # Adding custom widgets for better user experience.
        widgets = {
            'text': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Enter a word, phrase, or sentence...'}),
            'translation': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Optional: Enter the English translation...'}),
            'contributor_name': forms.TextInput(attrs={'placeholder': 'Optional: Your name'}),
            'contributor_location': forms.TextInput(attrs={'placeholder': 'Optional: Your location'}),
        }
        # Providing help text directly in the form is another option.
        labels = {
            'text': 'Contribution (Word/Phrase/Sentence)',
            'translation': 'English Translation',
            'contributor_name': 'Your Name',
            'contributor_location': 'Your Community/Location',
        }
