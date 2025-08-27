import phonenumbers
from django import forms
from django.core.exceptions import ValidationError
from .models import Product

def validate_african_number(value):
    """Validates an African mobile number format."""
    try:
        # Parse the number with a region code of 'ZZ' for unknown region
        # This allows the library to guess the country based on the number itself
        parsed_number = phonenumbers.parse(value, "ZZ")

        # Check if the number is a valid mobile number and is from an African country
        is_valid_number = phonenumbers.is_valid_number(parsed_number)
        is_mobile_or_fixed = phonenumbers.is_possible_number(parsed_number)

        # Check if the country code is within the African continent
        # The phonenumbers library doesn't have a direct 'is_from_africa' check,
        # so we'll check against a list of country codes for Africa.
        # Here's a simple, but not exhaustive, check:
        african_country_codes = [
            20, 27, 212, 213, 216, 218, 220, 221, 222, 223, 224, 225, 226,
            227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239,
            240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252,
            253, 254, 255, 256, 257, 258, 260, 261, 262, 263, 264, 265, 266,
            267, 268, 269, 290, 291, 297, 298, 299, 599, 672, 673, 674, 675,
            676, 677, 678, 679, 680, 681, 682, 683, 685, 686, 687, 688, 689,
            690, 691, 692, 693, 694, 695, 696, 697, 698, 699, 850, 852, 853,
            855, 856, 86, 870, 878, 880, 886, 960, 961, 962, 963, 964, 965,
            966, 967, 968, 971, 972, 973, 974, 975, 976, 977, 98, 992, 993,
            994, 995, 996, 998
        ]
        
        is_african = phonenumbers.get_country_code_for_region(phonenumbers.region_code_for_number(parsed_number)) in african_country_codes
        
        if not (is_valid_number and is_african):
            raise ValidationError(
                'Enter a valid phone number from an African country. Please include the full country code, e.g., +2348012345678.'
            )
    except phonenumbers.phonenumberutil.NumberParseException:
        raise ValidationError(
            'Enter a valid phone number from an African country. Please include the full country code, e.g., +2348012345678.'
        )

class ProductForm(forms.ModelForm):
    whatsapp_number = forms.CharField(validators=[validate_african_number])

    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'is_negotiable', 'vendor_name', 'whatsapp_number', 'tiktok_url', 'image', 'language_tag']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe your product...'}),
        }