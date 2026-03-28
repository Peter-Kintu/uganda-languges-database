from django import forms
from .models import BusinessReel, SecureMessage

class BusinessReelUploadForm(forms.ModelForm):
    """
    Pillar 3: The 'Agentic' Upload Form.
    Binds directly to BusinessReel model to handle AI negotiation floors.
    Now supports both Professional (no price) and Business (priced) content.
    """
    class Meta:
        model = BusinessReel
        # Explicitly defining fields to ensure security of the AI Floor Price
        fields = [
            'video', 
            'caption', 
            'price', 
            'currency', 
            'floor_price', 
            'is_low_bandwidth_optimized'
        ]
        
        widgets = {
            'caption': forms.Textarea(attrs={
                'placeholder': 'Describe your product, service, or professional work...', 
                'rows': 3,
                'class': 'w-full bg-gray-900 border-gray-700 rounded-2xl text-white p-4 focus:ring-2 focus:ring-indigo-500 transition-all placeholder:text-gray-600'
            }),
            'price': forms.NumberInput(attrs={
                'placeholder': 'Public Price (Leave blank for Professional/Work Samples)',
                'class': 'w-full bg-gray-900 border-gray-700 rounded-2xl text-white p-4 focus:ring-2 focus:ring-indigo-500 transition-all'
            }),
            'floor_price': forms.NumberInput(attrs={
                'placeholder': 'AI Minimum (Hidden from buyers)',
                'class': 'w-full bg-gray-900 border-indigo-900 rounded-2xl text-white p-4 focus:ring-2 focus:ring-indigo-500 transition-all shadow-[0_0_15px_rgba(79,70,229,0.1)]'
            }),
            'currency': forms.Select(attrs={
                'class': 'w-full bg-gray-900 border-gray-700 rounded-2xl text-white p-4'
            }),
            'is_low_bandwidth_optimized': forms.CheckboxInput(attrs={
                'class': 'w-6 h-6 rounded border-gray-700 text-indigo-600 focus:ring-indigo-500 bg-gray-900'
            }),
        }
        
        labels = {
            'price': 'Public Price (Optional)',
            'floor_price': 'AI Agent Floor Price (Optional)',
            'is_low_bandwidth_optimized': 'Optimize for Low Data (3G/4G)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Explicitly marking pricing as optional for Professional/Freelancer reels
        self.fields['price'].required = False
        self.fields['floor_price'].required = False
        self.fields['currency'].required = False

    def clean_video(self):
        """
        Pillar 2 Optimization:
        Ensures video files are within the 50MB stability threshold for African networks.
        """
        video = self.cleaned_data.get('video')
        if video:
            if video.size > 50 * 1024 * 1024:
                raise forms.ValidationError("Video file too large. Please keep it under 50MB for reliable delivery.")
        return video

    def clean(self):
        """
        Agentic Safety Protocol: 
        Ensures the AI Agent has a valid negotiation range if prices are set.
        """
        cleaned_data = super().clean()
        price = cleaned_data.get("price")
        floor_price = cleaned_data.get("floor_price")

        # Validation logic only triggers if the user is attempting a "Business" upload with prices
        if price is not None and floor_price is not None:
            if floor_price > price:
                raise forms.ValidationError(
                    "Safety Check: Your AI Floor Price cannot be higher than your Public Price. "
                    "The Agent needs room to bargain!"
                )
        
        # Logic check: If floor is set but price is not, assume floor is the public price
        if floor_price and not price:
             cleaned_data['price'] = floor_price
             
        return cleaned_data


class SecureMessageForm(forms.ModelForm):
    """
    Sovereign Messaging: The 'Hire' Protocol Form.
    Universal contact gateway for both Business inquiries and Professional hiring.
    """
    class Meta:
        model = SecureMessage
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'placeholder': 'Inquire about this service, propose a deal, or request a quote...',
                'rows': 3,
                'class': 'w-full bg-gray-900 border-gray-700 rounded-2xl text-white p-4 focus:ring-2 focus:ring-indigo-500 transition-all'
            }),
        }
        labels = {
            'content': 'Secure Message'
        }