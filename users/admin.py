from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser, Experience, Education, Skill

# --- Inline Admin for Profile Sections ---

class ExperienceInline(admin.TabularInline):
    model = Experience
    extra = 1 # Number of empty forms to display

class EducationInline(admin.TabularInline):
    model = Education
    extra = 1

class SkillInline(admin.TabularInline):
    model = Skill
    extra = 3

# --- Custom User Admin ---

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'headline', 'location']
    list_filter = ['is_staff', 'is_active', 'is_superuser']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'headline']
    ordering = ['username']
    
    # Field sets for the change form
    fieldsets = UserAdmin.fieldsets + (
        ('Profile Information', {'fields': ('headline', 'about', 'location', 'profile_image')}),
    )
    # Field sets for the add form
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Profile Information', {'fields': ('email', 'first_name', 'last_name', 'headline', 'location')}),
    )

    inlines = [
        ExperienceInline, 
        EducationInline, 
        SkillInline
    ]

# --- Register Other Models (Optional, since they are inlines, but good practice) ---
# Note: Since they are managed via inlines on CustomUser, explicit registration 
# is usually not needed unless you want a separate page for them.
# admin.site.register(Experience)
# admin.site.register(Education)
# admin.site.register(Skill)