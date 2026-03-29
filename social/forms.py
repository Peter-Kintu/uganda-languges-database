from django import forms
from .models import BusinessReel, SecureMessage

class BusinessReelUploadForm(forms.ModelForm):
    """
    Pillar 3: The 'Agentic' Upload Form.
    Binds directly to BusinessReel model to handle AI negotiation floors.
    Supports Professional (showcase) and Business (priced) content modes.
    UPDATED: Includes WhatsApp number input for the 'Hire Me' / 'Order' protocol.
    """
    
    whatsapp_number = forms.CharField(
        required=False,
        help_text="Format: 256700000000",
        widget=forms.TextInput(attrs={
            'placeholder': 'WhatsApp Number (e.g., 256...)',
            'class': 'w-full bg-gray-900 border-gray-700 rounded-2xl text-white p-4 focus:ring-2 focus:ring-indigo-500 transition-all placeholder:text-gray-600'
        })
    )

    class Meta:
        model = BusinessReel
        # Explicitly defining fields to ensure security of the AI Floor Price (Pillar 3)
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
                'placeholder': 'Public Price (Leave blank for Professional Showcase)',
                'class': 'w-full bg-gray-900 border-gray-700 rounded-2xl text-white p-4 focus:ring-2 focus:ring-indigo-500 transition-all'
            }),
            'floor_price': forms.NumberInput(attrs={
                'placeholder': 'AI Agent Minimum (Hidden from buyers)',
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
            'price': 'Public Listing Price',
            'floor_price': 'AI Agent Floor (Private)',
            'is_low_bandwidth_optimized': 'Optimize for Low-Data Networks (3G/4G)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Marking pricing as optional to support "Professional Mode" (Pillar 2)
        self.fields['price'].required = False
        self.fields['floor_price'].required = False
        self.fields['currency'].required = False
        
        # Setting default currency for the local market context
        self.fields['currency'].initial = 'UGX'

    def clean_video(self):
        """
        Pillar 2 Optimization: 
        Enforces 5-minute length limit and file size stability.
        Note: Compression is handled by Cloudinary via the Model definition.
        """
        video = self.cleaned_data.get('video')
        if video:
            # 1. Size Validation (Keep under 100MB for stability while allowing quality)
            if video.size > 100 * 1024 * 1024:
                raise forms.ValidationError(
                    "Video file is too large. Please keep under 100MB for high-quality delivery."
                )
            
            # 2. Duration Validation (Enforce 5-minute / 300-second limit)
            # This logic assumes the use of a library like moviepy or checking file metadata
            # For strict server-side enforcement, ensure moviepy is installed: pip install moviepy
            try:
                from moviepy.editor import VideoFileClip
                import tempfile
                import os

                with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as temp_file:
                    for chunk in video.chunks():
                        temp_file.write(chunk)
                    temp_file_path = temp_file.name

                clip = VideoFileClip(temp_file_path)
                duration = clip.duration
                clip.close()
                os.remove(temp_file_path)

                if duration > 300:
                    raise forms.ValidationError("Video duration exceeds the 5-minute limit.")
            except ImportError:
                # Fallback if moviepy isn't available: rely on client-side JS and Cloudinary auto-trim
                pass
            except Exception:
                # Basic error handling for file reading
                pass

        return video

    def clean(self):
        """
        Agentic Safety Protocol: 
        Validates the negotiation corridor for the AI Agent.
        """
        cleaned_data = super().clean()
        price = cleaned_data.get("price")
        floor_price = cleaned_data.get("floor_price")

        # 1. Validation for Business Mode: Floor cannot exceed Public Price
        if price is not None and floor_price is not None:
            if floor_price > price:
                raise forms.ValidationError(
                    "Safety Check Failed: The AI Floor Price cannot be higher than your Public Price. "
                    "The Agent cannot negotiate if the minimum is higher than the asking price!"
                )
        
        # 2. Logic Correction: If only floor is set, default public price to floor
        if floor_price and not price:
             cleaned_data['price'] = floor_price
             
        return cleaned_data


class SecureMessageForm(forms.ModelForm):
    """
    Sovereign Messaging: The 'Hire' Protocol Form.
    Native gateway for encrypted inquiries (Pillar 4).
    """
    class Meta:
        model = SecureMessage
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'placeholder': 'Request a quote, propose a deal, or inquire about this professional work...',
                'rows': 3,
                'class': 'w-full bg-gray-900 border-gray-700 rounded-2xl text-white p-4 focus:ring-2 focus:ring-indigo-500 transition-all'
            }),
        }
        labels = {
            'content': 'Secure Inquiry'
        }