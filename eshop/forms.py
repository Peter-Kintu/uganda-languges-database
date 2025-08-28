import phonenumbers
from django import forms
from django.core.exceptions import ValidationError
from .models import Product

import phonenumbers
from django.core.exceptions import ValidationError
from phonenumbers.phonenumberutil import country_code_for_region, region_code_for_number

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
            267, 268, 269
        ]


        if not (is_valid_number and is_possible_number and code in african_country_codes):
            raise ValidationError(
                "Enter a valid phone number from an African country. Include the full country code, e.g., +256701234567."
            )

    except phonenumbers.NumberParseException:
        raise ValidationError(
            "Could not parse the phone number. Please include the full country code, e.g., +256701234567."
        )   

class ProductForm(forms.ModelForm):
    whatsapp_number = forms.CharField(validators=[validate_african_number])

    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'is_negotiable', 'vendor_name', 'whatsapp_number', 'tiktok_url', 'image', 'language_tag']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe your product...'}),
        }