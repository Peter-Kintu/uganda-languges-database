import phonenumbers
from django import forms
from django.core.exceptions import ValidationError
from phonenumbers.phonenumberutil import country_code_for_region, region_code_for_number
from .models import Product

def validate_african_number(value):
    """Validates an African mobile number format using phonenumbers library."""
    try:
        # Ensure value has a plus sign for parsing
        phone_to_parse = value if value.startswith('+') else '+' + value
        parsed_number = phonenumbers.parse(phone_to_parse, "ZZ")

        is_valid_number = phonenumbers.is_valid_number(parsed_number)
        is_possible_number = phonenumbers.is_possible_number(parsed_number)

        region = region_code_for_number(parsed_number)
        code = country_code_for_region(region)

        # Comprehensive list of African Country Calling Codes
        african_country_codes = [
            20, 27, 212, 213, 216, 218, 220, 221, 222, 223, 224, 225, 226,
            227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239,
            240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252,
            253, 254, 255, 256, 257, 258, 260, 261, 262, 263, 264, 265, 266,
            267, 268, 269, 509, 599, 
        ]

        if not is_valid_number or not is_possible_number or code not in african_country_codes:
            raise ValidationError(
                "Please enter a valid African WhatsApp number. Include the full country code, e.g., +256701234567."
            )

    except phonenumbers.NumberParseException:
        raise ValidationError(
            "Could not parse the phone number. Please include the full country code starting with +, e.g., +256701234567."
        )   

class NegotiationForm(forms.Form):
    """Form used in the AI price negotiation chat window."""
    user_message = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-4 bg-transparent text-gray-100 border-none focus:ring-0 placeholder-gray-500 text-sm md:text-base',
            'placeholder': 'Type your offer here...',
            'autocomplete': 'off'
        }),
        label=''
    )

class ProductForm(forms.ModelForm):
    """Form for vendors to list new products including referral rewards."""
    
    whatsapp_number = forms.CharField(
        validators=[validate_african_number],
        widget=forms.TextInput(attrs={
            'placeholder': '+256701234567',
            'class': 'w-full px-4 py-3 bg-gray-700 border-gray-600 rounded-lg text-gray-200 focus:ring-indigo-500'
        }),
        help_text="Include the full country code (e.g., +256). Only African numbers are accepted."
    )

    class Meta:
        model = Product
        fields = [
            'name',
            'description',
            'price',
            'currency',
            'referral_commission',  # Added for the referral system
            'is_negotiable',
            'vendor_name', 
            'whatsapp_number', 
            'tiktok_url', 
            'image',
            'country',
            'slug'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g., Hand-carved Luganda Drum',
                'class': 'w-full px-4 py-3 bg-gray-700 border-gray-600 rounded-lg text-gray-200 focus:ring-indigo-500'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4, 
                'placeholder': 'Describe your product...',
                'class': 'w-full px-4 py-3 bg-gray-700 border-gray-600 rounded-lg text-gray-200 focus:ring-indigo-500'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-gray-700 border-gray-600 rounded-lg text-gray-200 focus:ring-indigo-500',
                'placeholder': '0.00'
            }),
            'currency': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-gray-700 border-gray-600 rounded-lg text-gray-200 focus:ring-indigo-500'
            }),
            'referral_commission': forms.NumberInput(attrs={
                'placeholder': 'Amount to pay per referral',
                'class': 'w-full px-4 py-3 bg-gray-700 border-indigo-500/50 rounded-lg text-emerald-400 focus:ring-emerald-500 font-bold'
            }),
            'country': forms.TextInput(attrs={
                'placeholder': 'e.g., Uganda',
                'class': 'w-full px-4 py-3 bg-gray-700 border-gray-600 rounded-lg text-gray-200 focus:ring-indigo-500'
            }),
            'vendor_name': forms.TextInput(attrs={
                'placeholder': 'e.g., Maama Tendo Crafts',
                'class': 'w-full px-4 py-3 bg-gray-700 border-gray-600 rounded-lg text-gray-200 focus:ring-indigo-500'
            }),
            'tiktok_url': forms.TextInput(attrs={
                'placeholder': 'https://www.tiktok.com/@yourprofile/video/...',
                'class': 'w-full px-4 py-3 bg-gray-700 border-gray-600 rounded-lg text-gray-200 focus:ring-indigo-500'
            }),
            'slug': forms.TextInput(attrs={
                'placeholder': 'Leave blank to auto-generate',
                'class': 'w-full px-4 py-3 bg-gray-700 border-gray-600 rounded-lg text-gray-200 focus:ring-indigo-500 italic text-sm'
            }),
            'is_negotiable': forms.CheckboxInput(attrs={
                'class': 'w-6 h-6 rounded border-gray-600 bg-gray-700 text-indigo-600 focus:ring-indigo-500'
            }),
        }

    def clean_whatsapp_number(self):
        value = self.cleaned_data.get('whatsapp_number')
        if not value:
            return value
        
        if not value.startswith('+'):
            value = '+' + value

        try:
            parsed = phonenumbers.parse(value, None)
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            return value