from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse
import json
import os
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime # ADDED THIS IMPORT for current context

# Import the Custom Forms and Models from our new app
from .forms import CustomUserCreationForm, ProfileEditForm
# Ensure SocialConnection is imported for the new functionality
from .models import CustomUser, Experience, Education, Skill, SocialConnection 


# ==============================================================================
# AUTHENTICATION VIEWS (UNCHANGED)
# ==============================================================================

def user_login(request):
    """Handles user login."""
    if request.user.is_authenticated:
        return redirect('languages:browse_job_listings')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect(request.POST.get('next') or reverse('users:profile')) 
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid form submission.")
            
    form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})

def user_register(request):
    """Handles user registration."""
    if request.user.is_authenticated:
        return redirect('users:profile')
        
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Auto-login the user after registration
            login(request, user)
            messages.success(request, "Registration successful. Welcome to Career Companion!")
            return redirect('users:profile')
        else:
            # Add form errors to messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'users/register.html', {'form': form})

@login_required
def user_logout(request):
    """Logs the user out and redirects to the login page."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('users:user_login')

# ==============================================================================
# PROFILE VIEWS
# ==============================================================================

@login_required
def user_profile(request):
    """Displays the user's main profile with their career data."""
    # The user object is request.user (instance of CustomUser)
    user = request.user
    
    # Retrieve related models data
    experiences = Experience.objects.filter(user=user).order_by('-start_date')
    educations = Education.objects.filter(user=user).order_by('-start_date')
    skills = Skill.objects.filter(user=user)
    social_connections = SocialConnection.objects.filter(user=user)

    context = {
        'user': user,
        'experiences': experiences,
        'educations': educations,
        'skills': skills,
        'social_connections': social_connections,
    }
    return render(request, 'users/profile.html', context)

@login_required
def profile_edit(request):
    """Handles editing the user's profile information."""
    user = request.user
    
    if request.method == 'POST':
        # Initialize the form with the user instance and POST data
        form = ProfileEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('users:profile')
        else:
            # Add form errors to messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = ProfileEditForm(instance=user)
        
    context = {
        'form': form
    }
    return render(request, 'users/profile_edit.html', context)

# ==============================================================================
# AI PROFILE CONTEXT UTILITIES (NEW)
# ==============================================================================

def _get_user_profile_data(user):
    """
    Gathers all relevant user profile data into a single,
    JSON-serializable dictionary for the AI.
    """
    profile_data = {
        "username": user.username,
        "full_name": user.get_full_name(),
        "email": user.email,
        # Safely access attributes that might be missing on the CustomUser model
        "location": getattr(user, 'location', None), 
        "bio": getattr(user, 'bio', None), 
        "headline": getattr(user, 'headline', None),
        "profile_image_url": user.profile_image.url if user.profile_image else None,
        "experiences": [
            {
                "title": exp.title,
                "company": exp.company,
                "start_date": exp.start_date.isoformat(),
                "end_date": exp.end_date.isoformat() if exp.end_date else "Present",
                "description": exp.description,
            }
            for exp in Experience.objects.filter(user=user).order_by('-start_date')
        ],
        "education": [
            {
                "institution": edu.institution,
                "degree": edu.degree,
                "start_date": edu.start_date.isoformat(),
                "end_date": edu.end_date.isoformat() if edu.end_date else "Ongoing",
            }
            for edu in Education.objects.filter(user=user).order_by('-start_date')
        ],
        "skills": [skill.name for skill in Skill.objects.filter(user=user)],
        "social_links": [
            {"platform": conn.platform, "url": conn.url}
            for conn in SocialConnection.objects.filter(user=user)
        ],
    }
    return profile_data

def _fetch_external_content(social_connections):
    """
    Attempts to fetch content from the user's social connections for AI context.
    NOTE: This is a PLACEHOLDER for a real-world implementation that would
    use an authenticated, rate-limited, and safe external API service.
    For this project, we'll simulate the successful fetch.
    """
    external_data = []
    # In a real app, you would use os.environ to check a secret
    # if not os.environ.get('ENABLE_EXTERNAL_FETCH', '0') == '1':
    #     return external_data 

    for connection in social_connections:
        # Simulate fetching content for links
        url = connection.url
        status = "Success (Simulated)"
        content = f"Simulated content from {connection.platform} at {url}..."

        external_data.append({
            "platform": connection.platform,
            "url": connection.url,
            "fetch_status": status,
            "raw_content": content if content else ""
        })
    return external_data


def _clean_history(messages):
    """
    Clean the chat history format for the Gemini API.
    1. Standardizes role: 'Ai' -> 'model', 'user' remains 'user'
    2. Standardizes content: 'text' property is moved into 'parts' array.
    """
    cleaned = []
    for msg in messages:
        # Standardize role: 'Ai' -> 'model'
        role = msg.get("role", "").lower()
        if role == "ai":
            role = "model"
        
        # Skip messages without a role or text for safety
        text_content = msg.get("text")
        if not role or not text_content:
            continue
        
        # Structure the content for the API: {"role": ..., "parts": [{"text": ...}]}
        cleaned.append({
            "role": role,
            "parts": [{"text": text_content}]
        })
    return cleaned

# ==============================================================================
# AI CHAT PROXY VIEWS
# ==============================================================================

# Assuming a tts_proxy function exists elsewhere or is a placeholder
def tts_proxy(request):
    """ 
    Placeholder for Text-to-Speech proxy view. 
    Actual implementation would use a TTS API.
    """
    return JsonResponse({"error": "TTS proxy not fully implemented."}, status=501)


@csrf_exempt
@login_required
def gemini_proxy(request):
    """ 
    Proxies chat requests to the Gemini API, now including external profile data.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST requests are allowed."}, status=405)

    try:
        # 1. Parse Request Body
        data = json.loads(request.body)
        contents = data.get('contents', [])
        config = data.get('config', {}) # To allow custom configs like temperature
        
        # 2. Setup API Key and Model
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return JsonResponse({"error": "GEMINI_API_KEY environment variable not set."}, status=500)
        
        # Use the most capable model for complex reasoning and context
        model_name = "gemini-2.5-flash" 
        url = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={api_key}"

        # 3. Gather Context
        user = request.user
        profile_data = _get_user_profile_data(user)
        social_connections = SocialConnection.objects.filter(user=user)
        external_data = _fetch_external_content(social_connections)

        # 4. Construct System Instruction
        profile_context_json = json.dumps(profile_data, indent=2)
        external_data_json = json.dumps(external_data, indent=2)

        # Define the generation config (defaults if not provided in POST)
        generation_config = {
            "temperature": config.get("temperature", 0.7),
            "maxOutputTokens": config.get("maxOutputTokens", 2048),
        }
        
        system_instruction_content = (
            "You are the Career Companion AI, an expert career advisor and job coach. "
            "Your role is to provide personalized, professional, and actionable advice "
            "based *EXCLUSIVELY* on the user's profile data and their conversation history. "
            "Do not fabricate information. When referencing the user's details, you must "
            "synthesize them into natural language; do not repeat the raw JSON.\n\n"
            "Capabilities:\n"
            "1. CV/Resume/Cover Letter Review and Optimization based on experience and education.\n"
            "2. Interview Practice: Pose relevant questions and provide feedback based on their profile.\n"
            "3. Career Path Guidance: Suggest next steps, skills to learn, or relevant job types.\n\n"
            "User Profile Data (for context only):\n"
            f"{profile_context_json}\n\n"
            "External Link Data (Simulated/Scraped Context):\n"
            f"{external_data_json}\n\n"
            "Current Context:\n"
            f"- Local Date/Time: {datetime.now().isoformat()}\n\n"
            "**USER CHAT HISTORY:**\n"
        )
        
        # 5. Build the API Payload
        # The first item in the contents array for the API must be the system instruction
        # to ensure it's treated as model-specific guidance.
        payload = {
            "contents": _clean_history(contents),
            "config": {
                "systemInstruction": system_instruction_content,
                "temperature": generation_config["temperature"],
                "maxOutputTokens": generation_config["maxOutputTokens"],
            }
        }
        
        # 6. Make the API Request
        resp = requests.post(url, json=payload)
        
        # 7. Error Handling
        if resp.status_code != 200:
            # CRITICAL LOG: This will show the exact reason for the 400 error.
            print("Gemini API Error Details:", resp.text)
            return JsonResponse(
                {"error": f"Gemini API error {resp.status_code}", "details": resp.text},
                status=resp.status_code,
            )

        # 8. Success Response Handling
        data = resp.json()
        text = ""
        if "candidates" in data and data["candidates"]:
            # Extracting text from parts, accommodating multiple parts if they exist
            parts = data["candidates"][0].get("content", {}).get("parts", [])
            text = " ".join(p.get("text", "") for p in parts if "text" in p)

        return JsonResponse({"text": text, "raw": data})

    except Exception as e:
        # CRITICAL LOG: For unexpected errors like JSON parsing or connection issues
        print("Unexpected Error in gemini_proxy:", str(e))
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def ai_quiz_generator(request):
    """Placeholder view for the AI Quiz Generator page."""
    context = {'user': request.user}
    return render(request, 'users/profile_ai.html', context)