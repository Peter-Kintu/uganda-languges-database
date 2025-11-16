import phonenumbers
from django import forms
from django.core.exceptions import ValidationError
from phonenumbers.phonenumberutil import country_code_for_region, region_code_for_number
from .models import Product

def validate_african_number(value):
    """Validates an African mobile number format."""
    try:
        parsed_number = phonenumbers.parse(value, "ZZ")

        is_valid_number = phonenumbers.is_valid_number(parsed_number)
        is_possible_number = phonenumbers.is_possible_number(parsed_number)

        region = region_code_for_number(parsed_number)
        code = country_code_for_region(region)

        african_country_codes = [
            20, 27, 212, 213, 216, 218, 220, 221, 222, 223, 224, 225, 226,
            227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239,
            240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252,
            253, 254, 255, 256, 257, 258, 260, 261, 262, 263, 264, 265, 266,
            267, 268, 269, 509, 599, # Added Haiti (509) and Curaçao/St Maarten (599) for broad coverage
        ]

        # Check if the number is valid/possible AND the country code is African
        if not is_valid_number or not is_possible_number or code not in african_country_codes:
            raise ValidationError(
                "Please enter a valid African WhatsApp number. Include the full country code, e.g., +256701234567."
            )

    except phonenumbers.NumberParseException:
        raise ValidationError(
            "Could not parse the phone number. Please include the full country code, e.g., +256701234567."
        )   

# --- Fix: Renamed UserMessageForm to NegotiationForm ---
class NegotiationForm(forms.Form):
    user_message = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Enter your offer or question...', 'class': 'w-full px-4 py-3 bg-gray-700 text-gray-200 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500'}),
        label=''
    )
# ----------------------------------------------------

class ProductForm(forms.ModelForm):
    whatsapp_number = forms.CharField(
    validators=[validate_african_number],
    widget=forms.TextInput(attrs={'placeholder': '+256701234567'}),
    help_text="Include the full country code. Only African numbers are accepted."
)
    class Meta:
        model = Product
        fields = ['name',
                 'description',
                 'price', 
                 'is_negotiable',
                'vendor_name', 
                'whatsapp_number', 
                'tiktok_url', 
                'image', 
                'language_tag',  
                'slug', 
                ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe your product...'}),
        }
    def clean_whatsapp_number(self):
       value = self.cleaned_data.get('whatsapp_number')
       if not value:
          return value
       try:
           parsed = phonenumbers.parse(value, "ZZ")
           # Convert to E.164 format for consistent storage
           return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
       except phonenumbers.NumberParseException:
           return value