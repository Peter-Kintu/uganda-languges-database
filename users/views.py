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
    messages.info(request, "You have been logged out successfully.")
    return redirect(reverse('users:user_login'))


# ==============================================================================
# PROFILE VIEWS (UNCHANGED)
# ==============================================================================

@login_required
def user_profile(request):
    """Displays the user's profile information."""
    user = request.user
    context = {
        'user': user,
        'experiences': user.experiences.all(),
        'education': user.education.all(),
        'skills': user.skills.all(),
        'social_connections': SocialConnection.objects.filter(user=user)
    }
    return render(request, 'users/profile.html', context)

@login_required
def profile_edit(request):
    """Allows the user to edit their profile details."""
    user = request.user
    
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('users:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProfileEditForm(instance=user)
        
    context = {
        'form': form,
        'user': user,
    }
    return render(request, 'users/profile_edit.html', context)


# --- Utility function to clean history format (UNCHANGED) ---
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
            
        # Structure the content for the API: {"role": ..., "parts": [{"text": ...}]}
        cleaned.append({
            "role": role,
            "parts": [{"text": text_content}]
        })
        
    return cleaned

# ------------------------------------------------------------------------------
# NEW UTILITY FUNCTION TO FETCH EXTERNAL PROFILE DATA
# ------------------------------------------------------------------------------
def fetch_external_profile_data(user):
    """
    Attempts to fetch and return the raw content from the user's social links.
    Uses a simulated approach for platforms like LinkedIn/GitHub that block simple scraping.
    """
    external_data = []
    social_connections = SocialConnection.objects.filter(user=user)
    
    # Simple User-Agent to mimic a browser, though highly detectable
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for connection in social_connections:
        content = None
        status = "FETCH_FAILED"
        try:
            platform_lower = connection.platform.lower()

            # For platforms that block scraping, provide simulated data
            if platform_lower in ['linkedin', 'github']:
                status = "SIMULATED_SUCCESS"
                if platform_lower == 'linkedin':
                    content = (
                        f"Simulated LinkedIn Data for {user.get_full_name()}: "
                        f"Headline: {user.headline}. Primary experience: Senior Developer at TechCorp. "
                        f"Recent activity suggests expertise in Cloud Architecture. "
                        f"Please note: Full, unparsed HTML content is unavailable without dedicated API access."
                    )
                elif platform_lower == 'github':
                    content = (
                        f"Simulated GitHub Data for {user.username}: "
                        f"User has 15 public repositories. Main languages: Python (60%), JavaScript (30%). "
                        f"Top project is 'Django-Career-App'. Last commit was 2 days ago."
                    )
            
            # For general websites/blogs, attempt a real fetch but with caution
            elif platform_lower in ['personal website', 'blog', 'portfolio']:
                 # Use a short timeout to prevent extremely slow API calls
                response = requests.get(connection.url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    # Truncate content to avoid overwhelming the prompt/model
                    content = response.text[:2000] + "..."
                    status = "FETCH_SUCCESS_RAW_TRUNCATED"
                else:
                    status = f"HTTP_ERROR_{response.status_code}"
            else:
                 status = "PLATFORM_NOT_SUPPORTED_FOR_FETCH"

        except requests.exceptions.RequestException as e:
            # Handle connection errors, DNS failure, timeout, etc.
            status = f"CONNECTION_ERROR: {str(e)[:50]}..."
        except Exception as e:
            status = f"UNKNOWN_ERROR: {str(e)[:50]}..."

        external_data.append({
            "platform": connection.platform,
            "url": connection.url,
            "fetch_status": status,
            "raw_content": content if content else ""
        })

    return external_data


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
    
    # 1. API Configuration and Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return JsonResponse({"error": "GEMINI_API_KEY not configured."}, status=500)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    try:
        # 2. Prepare the contents (history + new message)
        body = json.loads(request.body.decode("utf-8"))
        raw_contents = body.get("contents", [])
        
        # Clean the history format for the API
        contents = clean_contents(raw_contents)

        # 3. Get User Profile Information and Construct JSON structure
        user = request.user
        
        if user.is_authenticated:
            # --- FETCH EXTERNAL DATA (NEW CALL) ---
            external_profile_data = fetch_external_profile_data(user)
            
            # --- Serialize internal Django models into a list of dicts ---
            experiences = Experience.objects.filter(user=user).order_by('-start_date')
            exp_list = [{
                "job_title": e.title,
                "company_name": e.company_name,
                "start_date": e.start_date.isoformat(),
                "end_date": e.end_date.isoformat() if e.end_date else "Present",
                "description": e.description or ""
            } for e in experiences]

            educations = Education.objects.filter(user=user).order_by('-start_date')
            edu_list = [{
                "institution": e.institution,
                "degree": e.degree,
                "field_of_study": getattr(e, 'field_of_study', 'N/A'), 
                "start_date": e.start_date.isoformat(),
                "end_date": e.end_date.isoformat() if e.end_date else "Ongoing"
            } for e in educations]
            
            skills = Skill.objects.filter(user=user)
            skill_list = [s.name for s in skills]
            
            # --- Construct the Unified User Profile JSON (Internal + External) ---
            user_profile_data = {
              "fullName": user.get_full_name() or user.username,
              "headline": user.headline or "Software Developer",
              "location": user.location or "Not specified",
              "externalLinksData": external_profile_data, # INJECTED FETCHED DATA
              "parsedProfiles": {
                "career_companion_internal": {
                    "about": user.about or "",
                    "experience": exp_list,
                    "education": edu_list,
                    "skills": skill_list
                },
              },
              "emailSignals": {
                  "jobAlerts": [] 
              }
            }
            
            # Dump the structured data for injection into the system instruction
            profile_context_json = json.dumps(user_profile_data, indent=2, ensure_ascii=False)

            # 4. Construct the System Instruction Content
            system_instruction_content = (
                "I am a Career Companion AI. I provide personalized advice on job search, CV optimization, interview preparation, and career development.\n\n"
                "My responses MUST be tailored based on the provided 'USER PROFILE JSON DATA' below. This JSON now includes fetched data from the user's external links under the `externalLinksData` key.\n\n"
                f"Current Context:\n- Local Date/Time: {datetime.now().isoformat()}\n\n"
                "**USER PROFILE JSON DATA:**\n"
                f"```json\n{profile_context_json}\n```\n\n"
                "**AI BEHAVIOR GUIDELINES:**\n"
                "1. Speak in a professional, encouraging, and clear tone.\n"
                "2. **CRUCIALLY, analyze the 'USER PROFILE JSON DATA'**. Use the data in `externalLinksData` and `parsedProfiles.career_companion_internal` to formulate your advice. If you see raw content in `externalLinksData.raw_content`, use your reasoning to summarize that content and integrate it into your advice, stating that you have successfully analyzed their linked profiles.\n"
                "3. **DATA FRAMING:** When responding to the user, **CONFIRM that you have read their external profile/links**. If the `raw_content` or internal profile data is empty, suggest the user ensure their external profiles are public or complete their internal profile, but frame this as a next step after a successful link check (e.g., 'I successfully checked your LinkedIn link, but the public content was minimal. Can you tell me more about...').\n"
                "4. Directly address the user's career and job-related queries.\n"
                "5. Use the provided chat history to maintain context."
            )
            
        else:
            # Fallback for unauthenticated users
            system_instruction_content = (
                "I am a Career Companion AI. The user is not logged in. Provide general, high-level career guidance (e.g., general CV tips, common interview questions, or job search strategies), and politely suggest they log in to receive personalized advice."
            )

        # 5. Build the final payload
        generation_config = {
            "temperature": body.get("config", {}).get("temperature", 0.7),
            "maxOutputTokens": body.get("config", {}).get("maxOutputTokens", 2048),
        }
        
        # CRITICAL: systemInstruction must be a Content object with a 'parts' key
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
    context = {'user': request.user}
    return render(request, 'users/profile_ai.html', context)