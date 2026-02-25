from django import forms
from .models import Accommodation

class AccommodationForm(forms.ModelForm):  # FIXED: Removed the underscore
    class Meta:
        model = Accommodation
        # These fields match the ones used in your add_accommodation.html template
        # UPDATED: Added latitude and longitude for the 5KM Discovery Engine
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
            'description',
            'latitude',
            'longitude'
        ]
        
        # Adding styling widgets to match your dark-mode UI
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4, 
                'placeholder': 'Describe the lodge...',
                'class': 'w-full bg-white/5 border border-white/10 rounded-2xl px-6 py-4 text-white focus:outline-none focus:border-indigo-500 transition-all'
            }),
            'price_per_night': forms.NumberInput(attrs={'step': '1'}),
            # Hidden or Readonly widgets for GPS data to prevent manual typing errors
            'latitude': forms.TextInput(attrs={
                'readonly': 'readonly', 
                'placeholder': 'Lat',
                'class': 'bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-[10px] text-indigo-400 font-mono'
            }),
            'longitude': forms.TextInput(attrs={
                'readonly': 'readonly', 
                'placeholder': 'Lon',
                'class': 'bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-[10px] text-indigo-400 font-mono'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We ensure that manually added lodges are marked as 'local'
        if not self.instance.pk:
            self.instance.source = 'local'
            
        # Optional: Make GPS fields required to ensure the Discovery Engine works
        self.fields['latitude'].required = False
        self.fields['longitude'].required = False