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
from datetime import datetime

# Import the Custom Forms and Models from our new app
from .forms import CustomUserCreationForm, ProfileEditForm
from .models import CustomUser, Experience, Education, Skill # Imported for clarity, but generally accessed via request.user


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
            messages.error(request, "Registration failed. Please correct the errors below.")
    else:
        form = CustomUserCreationForm()

    context = {'form': form}
    return render(request, 'users/register.html', context)


@login_required
def user_logout(request):
    """Handles user logout."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('users:user_login')


# ==============================================================================
# PROFILE VIEWS
# ==============================================================================

@login_required
def user_profile(request):
    """Displays the user's full profile."""
    # The user object is available via request.user thanks to @login_required
    
    # FIX: Use explicit Model Manager lookup instead of reverse manager
    context = {
        'user': request.user,
        'experiences': Experience.objects.filter(user=request.user).order_by('-start_date'),
        'educations': Education.objects.filter(user=request.user).order_by('-start_date'),
        'skills': Skill.objects.filter(user=request.user),
    }
    return render(request, 'users/profile.html', context)


@login_required
def profile_edit(request):
    """Handles editing the user's profile and related models."""
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('users:profile')
        else:
            messages.error(request, "There was an error updating your profile. Please correct the errors.")
    else:
        form = ProfileEditForm(instance=request.user)

    context = {'form': form}
    # You will need to create a simple 'profile_edit.html' template
    return render(request, 'users/profile_edit.html', context)

# --- Utility function to clean history format ---
def clean_contents(messages):
    """ 
    Ensures messages conform to the Gemini API format:
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
            
        # Structure the content for the API
        # This correctly creates the {"role": ..., "parts": [{"text": ...}]} structure
        cleaned.append({
            "role": role,
            "parts": [{"text": text_content}]
        })
        
    return cleaned


# ==============================================================================
# AI CHAT PROXY VIEWS
# ==============================================================================

# TTS proxy is used to convert text to speech, typically from a separate API
@csrf_exempt
def tts_proxy(request):
    """A placeholder or simple proxy for Text-to-Speech API calls."""
    if request.method == 'POST':
        try:
            # Assuming the request body contains JSON with 'text' and 'voice'
            body = json.loads(request.body.decode('utf-8'))
            text_to_speak = body.get('text', '')
            # voice_config = body.get('voice', 'en-US-Standard-C') # Example voice parameter
            
            # TODO: Integrate with a real TTS API (e.g., Google Cloud TTS, Azure TTS)
            # For now, just a success response or error if text is missing
            if not text_to_speak:
                return JsonResponse({"error": "No text provided for TTS."}, status=400)
            
            # In a real implementation, this would call the external TTS API and stream back the audio
            # response. For a simple placeholder, we just log and return a 'successful' message.
            # print(f"TTS Request received for text: {text_to_speak[:50]}...")

            # --- Mock Response (replace with real API call) ---
            # response = requests.post(REAL_TTS_API_ENDPOINT, json={...})
            # return HttpResponse(response.content, content_type='audio/mpeg')
            
            return JsonResponse({"message": "TTS processing started (mock response)."}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON in request body."}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Only POST requests are allowed."}, status=405)


@csrf_exempt
@login_required
def gemini_proxy(request):
    """
    Proxies chat requests to the Gemini API, injecting the user's current profile
    and system context for personalized career advice.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST requests are allowed."}, status=405)
    
    # 1. API Configuration and Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return JsonResponse({"error": "GEMINI_API_KEY not configured."}, status=500)
    
    # Use a powerful model for complex career/profile analysis
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    try:
        # 2. Get User Profile Information for System Instruction
        user = request.user
        
        # Check if user is authenticated (should be guaranteed by @login_required but safe check)
        if user.is_authenticated:
            # Format Experience
            # FIX: Use explicit Model Manager lookup instead of reverse manager
            experiences = Experience.objects.filter(user=request.user).order_by('-start_date')
            exp_list = []
            for e in experiences:
                # Assuming end_date can be None or an empty string, and checking for it.
                end_year = e.end_date.year if e.end_date else 'Present'
                exp_list.append(
                    f"- {e.job_title} at {e.company}, {e.start_date.year}-{end_year}. Description: {e.description or 'N/A'}"
                )

            # Format Education
            # FIX: Use explicit Model Manager lookup instead of reverse manager
            educations = Education.objects.filter(user=request.user).order_by('-start_date')
            edu_list = []
            for e in educations:
                # Assuming end_date can be None or an empty string, and checking for it.
                end_year = e.end_date.year if e.end_date else 'Ongoing'
                edu_list.append(
                    f"- {e.degree} in {e.field_of_study} from {e.institution}, {e.start_date.year}-{end_year}"
                )

            # Format Skills
            # FIX: Use explicit Model Manager lookup instead of reverse manager
            skills = Skill.objects.filter(user=request.user)
            skill_list = [s.name for s in skills]
            
            # Combine all profile data into a dedicated string
            profile_context = f"""
- Full Name: {user.get_full_name() or user.username}
- Headline: {user.headline or 'Not provided'}
- Bio (Summary): {user.about or 'Not provided'}
- Location: {user.location or 'Not provided'}

**Experience:**
{chr(10).join(exp_list) or '- No experience listed.'}

**Education:**
{chr(10).join(edu_list) or '- No education listed.'}

**Skills:**
{', '.join(skill_list) or '- No skills added.'}
"""
        else:
            profile_context = "[User is not logged in. Provide general career guidance.]"


        # 3. Prepare the contents (history + new message)
        body = json.loads(request.body.decode("utf-8"))
        raw_contents = body.get("contents", [])
        
        # Clean the history format for the API (ensures {"role":..., "parts": [{"text":...}]} format)
        contents = clean_contents(raw_contents)

        # 4. Construct the system instruction content
        # FIX: Changed datetime formatting to isoformat and used explicit concatenation
        system_instruction_content = (
            "I am a Career Companion AI. I provide personalized advice on job search, CV optimization, interview preparation, and career development.\n\n"
            "My responses MUST be tailored based on the provided 'User Profile' data.\n\n"
            f"Current Context:\n- Local Date/Time: {datetime.now().isoformat()}\n- User Profile: \n{profile_context.strip()}\n\n"
            "You are expected to:\n"
            "1. Speak in a professional, encouraging, and clear tone.\n"
            "2. **Crucially, integrate the 'User Profile' data into your advice.** For example, if the user asks for CV tips, use their current experience/skills. If they ask for interview prep, use their job title/experience to tailor the questions.\n"
            "3. Directly address the user's career and job-related queries.\n"
            "4. Use the provided chat history to maintain context.\n"
            "5. If the user mentions their location, acknowledge it to provide geographically relevant advice."
        )


        # 5. Build the final payload
        generation_config = {
            "temperature": body.get("config", {}).get("temperature", 0.7),
            "maxOutputTokens": body.get("config", {}).get("maxOutputTokens", 2048),
        }
        
        # CRITICAL FIX: systemInstruction must be a Content object, not a raw string
        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [
                    {"text": system_instruction_content}
                ]
            },
            "generationConfig": generation_config,
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
    # This view simply renders the profile_ai.html template
    context = {'user': request.user}
    return render(request, 'users/profile_ai.html', context)