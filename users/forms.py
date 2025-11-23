from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, Experience, Education, Skill

# --- Authentication Forms ---

class CustomUserCreationForm(UserCreationForm):
    """
    A custom form for creating a new user, based on the CustomUser model.
    """
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'headline', 'location')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Tailwind classes to all form fields for consistent styling
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'w-full px-4 py-3 bg-gray-700 text-white border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder-gray-500'


# --- Profile Forms ---

class CustomUserChangeForm(UserChangeForm):
    """
    The form used for editing the user details in the admin.
    """
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'headline', 'location', 'profile_image')
        
        
class ProfileEditForm(forms.ModelForm):
    """
    Form for users to edit their profile details (headline, about, location).
    """
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'headline', 'about', 'location', 'profile_image')
        widgets = {
            'about': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell us about your professional journey...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'w-full px-4 py-3 bg-gray-700 text-white border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder-gray-500'