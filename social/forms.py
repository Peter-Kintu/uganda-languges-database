from django import forms
from .models import BusinessReel

class BusinessReelUploadForm(forms.ModelForm):
    """
    Pillar 3: The 'Agentic' Upload Form.
    Binds directly to BusinessReel model to handle AI negotiation floors.
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
                'placeholder': 'Describe your product or service...', 
                'rows': 3,
                'class': 'w-full bg-gray-900 border-gray-700 rounded-2xl text-white p-4 focus:ring-2 focus:ring-indigo-500 transition-all'
            }),
            'price': forms.NumberInput(attrs={
                'placeholder': 'Public Price (e.g. 50,000)',
                'class': 'w-full bg-gray-900 border-gray-700 rounded-2xl text-white p-4 focus:ring-2 focus:ring-indigo-500 transition-all'
            }),
            'floor_price': forms.NumberInput(attrs={
                'placeholder': 'AI Minimum (e.g. 45,000)',
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
            'floor_price': 'AI Agent Floor Price (Private)',
            'is_low_bandwidth_optimized': 'Optimize for Low Data (3G/4G)'
        }

    def clean_video(self):
        """
        Pillar 2 Optimization:
        Basic validation to ensure video files aren't massive before 
        attempting the Cloudinary upload.
        """
        video = self.cleaned_data.get('video')
        if video:
            # Limit to 50MB for mobile-first stability
            if video.size > 50 * 1024 * 1024:
                raise forms.ValidationError("Video file too large. Please keep it under 50MB.")
        return video

    def clean(self):
        """
        Agentic Safety Protocol: 
        Ensures the AI Agent cannot be instructed to sell at a 'floor' 
        that exceeds the advertised public price.
        """
        cleaned_data = super().clean()
        price = cleaned_data.get("price")
        floor_price = cleaned_data.get("floor_price")

        if price and floor_price:
            if floor_price > price:
                raise forms.ValidationError(
                    "Safety Check: Your AI Floor Price cannot be higher than your Public Price. "
                    "The Agent needs a range to negotiate within."
                )
            
            # Advice for the user: Encourage a margin for the AI to work with
            if floor_price == price:
                 # We don't raise an error, but this makes the 'Agent' useless.
                 # In a future update, we could add a warning message here.
                 pass

        return cleaned_data