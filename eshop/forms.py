import re
from django import forms
from django.core.exceptions import ValidationError
from .models import Product

def validate_ugandan_number(value):
    """Validates a Ugandan mobile number format."""
    ugandan_number_regex = re.compile(r'^(?:\+256|0)?7[0-9]{8}$')
    if not ugandan_number_regex.match(value):
        raise ValidationError(
            'Enter a valid Ugandan mobile number, e.g., +256771234567 or 0771234567.'
        )

class ProductForm(forms.ModelForm):
    whatsapp_number = forms.CharField(validators=[validate_ugandan_number])

    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'is_negotiable', 'vendor_name', 'whatsapp_number', 'tiktok_url', 'image', 'language_tag']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe your product...'}),
        }