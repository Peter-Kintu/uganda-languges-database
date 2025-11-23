from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse

# Import the Custom Forms and Models from our new app
from .forms import CustomUserCreationForm, ProfileEditForm
from .models import CustomUser, Experience, Education, Skill # Imported for clarity, but generally accessed via request.user


# ==============================================================================
# AUTHENTICATION VIEWS
# ==============================================================================

def user_login(request):
    """Handles user login."""
    if request.user.is_authenticated:
        return redirect('users:user_profile')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect(request.GET.get('next', reverse('users:profile')))
            else:
                # The AuthenticationForm handles this error automatically
                pass 
    else:
        form = AuthenticationForm()

    context = {'form': form}
    return render(request, 'users/login.html', context)


def user_register(request):
    """Handles user registration using the CustomUserCreationForm."""
    if request.user.is_authenticated:
        return redirect('users:profile')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST) 
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful! Now, complete your profile.")
            
            # Redirect to the edit page after registration for profile completion
            return redirect('users:profile_edit') 
    else:
        form = CustomUserCreationForm()
        
    context = {'form': form}
    return render(request, 'users/register.html', context)


@login_required
def user_logout(request):
    """Logs out the current user."""
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('users:user_login')


# ==============================================================================
# PROFILE VIEWS
# ==============================================================================

@login_required
def user_profile(request):
    """
    Displays the LinkedIn-style user profile page.
    Data is fetched dynamically via the user's related managers.
    """
    user = request.user
    
    context = {
        'user': user, 
        # The related_name attributes are used here (experiences, education, skills)
        'experiences': user.experiences.all().order_by('-start_date'),
        'education': user.education.all().order_by('-end_date'),
        'skills': user.skills.all(),
        # Other profile fields (name, headline, etc.) are accessed directly via {{ user.field_name }}
    }
    return render(request, 'users/profile.html', context)


@login_required
def profile_edit(request):
    """
    Handles editing the main fields of the CustomUser model.
    (Forms for Experience/Education/Skills would be separate views or managed with formsets)
    """
    if request.method == 'POST':
        # Pass request.FILES to handle the profile_image upload
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user) 
        if form.is_valid():
            form.save()
            messages.success(request, "Your core profile has been updated successfully!")
            return redirect('users:profile')
    else:
        form = ProfileEditForm(instance=request.user)
    
    context = {
        'form': form,
        'title': "Edit Your Profile",
    }
    # You will need to create a simple 'profile_edit.html' template
    return render(request, 'users/profile_edit.html', context)