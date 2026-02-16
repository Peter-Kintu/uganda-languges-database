from django import forms
from .models import Accommodation

class AccommodationForm(forms.ModelForm):  # FIXED: Removed the underscore
    class Meta:
        model = Accommodation
        # These fields match the ones used in your add_accommodation.html template
        fields = [
            'name', 
            'city', 
            'country', 
            'price_per_night', 
            'currency', 
            'stars', 
            'image', 
            'whatsapp_number', 
            'tiktok_url', 
            'description'
        ]
        
        # Adding styling widgets to match your dark-mode UI
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe the lodge...'}),
            'price_per_night': forms.NumberInput(attrs={'step': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We ensure that manually added lodges are marked as 'local'
        if not self.instance.pk:
            self.instance.source = 'local'