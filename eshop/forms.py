from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'is_negotiable', 'vendor_name', 'whatsapp_number', 'tiktok_url', 'image', 'language_tag']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }