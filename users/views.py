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
# AUTHENTICATION VIEWS
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
                # Use 'next' parameter for redirection after login, defaulting to a specified path
                return redirect(request.GET.get('next') or reverse('languages:browse_job_listings')) 
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
        
    context = {'form': form, 'title': 'Login'}
    return render(request, 'users/login.html', context)


def user_register(request):
    """Handles user registration."""
    if request.user.is_authenticated:
        return redirect('languages:browse_job_listings')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the user in immediately after successful registration
            login(request, user)
            messages.success(request, f"Account created for {user.username}. Welcome!")
            return redirect(reverse('users:profile_edit')) # Redirect to profile edit to complete profile
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomUserCreationForm()

    context = {'form': form, 'title': 'Register'}
    return render(request, 'users/register.html', context)


@login_required
def user_logout(request):
    """Logs out the current user."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect(reverse('users:user_login'))


# ==============================================================================
# PROFILE VIEWS
# ==============================================================================

@login_required
def user_profile(request):
    """Displays the user's complete profile."""
    user = request.user
    
    # Fetch related data for the profile template
    experiences = user.experiences.all() 
    education = user.education.all()
    skills = user.skills.all()
    social_connections = user.social_connection.all() # Fetch social connections
    
    context = {
        'user': user,
        'experiences': experiences,
        'education': education,
        'skills': skills,
        'social_connections': social_connections, # Pass to context
        'title': f"{user.get_full_name() or user.username}'s Profile"
    }
    return render(request, 'users/profile.html', context)


@login_required
def profile_edit(request):
    """Handles editing of the user's main profile and inlines for Experience/Education/Skills."""
    
    user = request.user
    
    if request.method == 'POST':
        # Pass request.FILES for profile_image handling
        form = ProfileEditForm(request.POST, request.FILES, instance=user)
        
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect(reverse('users:profile'))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProfileEditForm(instance=user)

    context = {
        'form': form,
        'title': 'Edit Profile',
    }
    return render(request, 'users/profile_edit.html', context)
    
# =============================================================================
# AI VIEWS
# =============================================================================

@csrf_exempt
def gemini_proxy(request):
    """
    Proxies a chat request to the Gemini API using request.user's profile
    data as context to the AI.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST requests are allowed."}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        # 1. Configuration
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return JsonResponse({"error": "Server configuration error: API key missing."}, status=500)

        # Model and URL
        model_name = "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        # 2. Extract Data from Request
        try:
            data = json.loads(request.body)
            # The client sends history as an array of objects: [{'role': 'user/model', 'text': '...'}]
            history = data.get("history", [])
            user_input = data.get("prompt", "")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format in request body."}, status=400)

        if not user_input:
            return JsonResponse({"error": "Prompt cannot be empty."}, status=400)

        # 3. Compile User Profile Context
        user = request.user
        
        # Build the structured profile data
        profile_data = {
            "name": user.get_full_name() or user.username,
            "username": user.username,
            "email": user.email,
            "headline": user.headline,
            "about": user.about,
            "location": user.location,
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"),
            "experiences": [
                {
                    "title": exp.title, 
                    "company": exp.company_name,
                    "duration": f"{exp.start_date.year} - {exp.end_date.year if exp.end_date else 'Present'}",
                    "description": exp.description
                } 
                for exp in user.experiences.all()
            ],
            "education": [
                {
                    "degree": edu.degree, 
                    "institution": edu.institution,
                    "duration": f"{edu.start_date.year} - {edu.end_date.year if edu.end_date else 'Ongoing'}"
                } 
                for edu in user.education.all()
            ],
            "skills": [skill.name for skill in user.skills.all()],
            # New context: Social Connections
            "social_connections": [
                {
                    "platform": conn.platform,
                    "url": conn.url
                }
                for conn in user.social_connection.all()
            ]
        }
        
        # Format the profile data into a string for the system instruction
        profile_context = json.dumps(profile_data, indent=2)

        # 4. System Instruction: The AI's role and context
        system_instruction_content = (
            "You are an expert Career Companion AI. Your primary goal is to assist the user with job searching, CV/resume optimization, interview preparation, and career guidance. You have access to the user's complete profile data. Use this data to provide highly personalized and relevant advice, suggestions, and answers. Do not reveal the raw JSON structure of the profile data. Only use the information for context. "
            f"USER'S CURRENT PROFILE DATA:\n{profile_context}"
        )
        
        # 5. Construct the Request Payload
        
        # Convert client history to model's 'contents' format
        # Filter out empty or None text values before creating the part object
        contents = []
        for item in history:
            text = item.get('text')
            role = item.get('role', 'user') # Default to user if role is missing/bad
            if text:
                contents.append({
                    "role": role if role in ['user', 'model'] else 'user', 
                    "parts": [{"text": text}]
                })

        # Add the current user prompt
        contents.append({"role": "user", "parts": [{"text": user_input}]})

        # Set up generation config (temperature for less factual, more creative/helpful responses)
        generation_config = {
            "temperature": 0.5,
            "maxOutputTokens": 2048,
        }
        
        # The main payload structure:
        payload = {
            # contents list already contains the history and the new user prompt
            "contents": contents,
            # PASS THE CORRECTLY STRUCTURED CONTENT OBJECT
            "systemInstruction": system_instruction_content, 
            "generationConfig": generation_config,
        }

        # Debug log: Log the final outbound payload before sending
        # print("Outbound Gemini payload:", json.dumps(payload, indent=2))

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
    """Placeholder view for the AI Quiz Generator page (maps to 'profile_ai' in urls.py)."""
    # This view simply renders the profile_ai.html template
    return render(request, 'users/profile_ai.html', {'title': 'AI Companion'})


# =============================================================================
# TEXT-TO-SPEECH PROXY
# =============================================================================

@csrf_exempt
def tts_proxy(request):
    """
    Proxies a text-to-speech request to a third-party API (e.g., Google Text-to-Speech).
    This is an API-key protected endpoint.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST requests are allowed."}, status=405)

    # 1. Check for API Key
    api_key = os.environ.get("TTS_API_KEY") # Replace with your actual TTS API key environment variable name
    if not api_key:
        return JsonResponse({"error": "Server configuration error: TTS API key missing."}, status=500)

    # 2. Extract Data from Request
    try:
        data = json.loads(request.body)
        text_to_speak = data.get("text", "")
        # Optional: voice_name = data.get("voice", "en-US-Wavenet-D")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format in request body."}, status=400)

    if not text_to_speak:
        return JsonResponse({"error": "Text to speak cannot be empty."}, status=400)

    # 3. Google Cloud Text-to-Speech API Configuration (Example)
    # The actual URL might vary. This is a generic example.
    tts_url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}" 
    
    tts_payload = {
        "input": {
            "text": text_to_speak
        },
        "voice": {
            "languageCode": "en-US",
            "name": "en-US-Standard-C" # A standard male voice
        },
        "audioConfig": {
            "audioEncoding": "MP3"
        }
    }

    # 4. Make the API Request
    try:
        resp = requests.post(tts_url, json=tts_payload)
        
        # 5. Error Handling
        if resp.status_code != 200:
            print("TTS API Error Details:", resp.text)
            return JsonResponse(
                {"error": f"TTS API error {resp.status_code}", "details": resp.text},
                status=resp.status_code,
            )
            
        # 6. Success Response Handling
        tts_data = resp.json()
        audio_content = tts_data.get("audioContent") # Base64 encoded audio

        if not audio_content:
             return JsonResponse({"error": "TTS API returned no audio content."}, status=500)

        # Return the Base64 audio content directly to the client
        return JsonResponse({"audio_content": audio_content})

    except requests.exceptions.RequestException as e:
        print("Network/Connection Error in tts_proxy:", str(e))
        return JsonResponse({"error": "Network or external API connection error."}, status=503)
    except Exception as e:
        print("Unexpected Error in tts_proxy:", str(e))
        return JsonResponse({"error": str(e)}, status=500)