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
                'placeholder': 'Public Price',
                'class': 'w-full bg-gray-900 border-gray-700 rounded-2xl text-white p-4 focus:ring-2 focus:ring-indigo-500 transition-all'
            }),
            'floor_price': forms.NumberInput(attrs={
                'placeholder': 'AI Minimum (Private)',
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
            'floor_price': 'AI Agent Floor Price',
            'is_low_bandwidth_optimized': 'Optimize for Low Data (3G/4G)'
        }

    def clean(self):
        """
        Agentic Safety Protocol: 
        Ensures the AI Agent cannot be instructed to sell at a 'floor' 
        that exceeds the advertised public price.
        """
        cleaned_data = super().clean()
        price = cleaned_data.get("price")
        floor_price = cleaned_data.get("floor_price")

        if price and floor_price and floor_price > price:
            # This error will be caught in the 'upload_reel' view and shown in the template
            raise forms.ValidationError(
                "The AI Negotiation Floor cannot be higher than the public price. "
                "Adjust the floor to be equal to or less than the Listing Price."
            )
        return cleaned_data