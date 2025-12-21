import os
import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.template import TemplateDoesNotExist
from datetime import datetime

# Official Google GenAI SDK imports (2025 Standard)
from google import genai
from google.genai import types

# Custom Forms and Models
from .models import CustomUser, Experience, Education, Skill, SocialConnection 
from .forms import CustomUserCreationForm, ProfileEditForm
from django.contrib.auth import get_user_model

User = get_user_model()

# Safely import eshop models
try:
    from eshop.models import Product, CartItem 
except ImportError:
    Product = None
    CartItem = None

# ==============================================================================
# UTILITY / INFRASTRUCTURE VIEWS
# ==============================================================================

def google_verification(request):
    """Verifies site ownership for Google Search Console."""
    return HttpResponse("google-site-verification: googlec0826a61eabee54e.html")

def robots_txt(request):
    """Generates robots.txt for search engine crawlers."""
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Sitemap: https://uganda-languges-database.onrender.com/sitemap.xml"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def tts_proxy(request):
    """Proxies TTS requests to avoid CORS issues."""
    text = request.GET.get('text', '')
    lang = request.GET.get('lang', 'en')
    if not text:
        return HttpResponse("No text provided", status=400)
    
    tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={text}&tl={lang}&client=tw-ob"
    try:
        response = requests.get(tts_url, stream=True, timeout=5)
        return HttpResponse(response.content, content_type="audio/mpeg")
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

# ==============================================================================
# AUTHENTICATION VIEWS
# ==============================================================================

def user_login(request):
    if request.user.is_authenticated:
        return redirect('languages:browse_job_listings')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url or reverse('languages:browse_job_listings')) 
        else:
            messages.error("Invalid username or password.")
    else:
        form = AuthenticationForm()
    context = {'form': form, 'next': request.GET.get('next', '')}
    try:
        return render(request, 'users/login.html', context)
    except TemplateDoesNotExist:
        return render(request, 'login.html', context)

def user_register(request):
    if request.user.is_authenticated:
        return redirect('languages:browse_job_listings')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful. Welcome to Africana!")
            return redirect('languages:browse_job_listings')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = CustomUserCreationForm()
    try:
        return render(request, 'users/register.html', {'form': form})
    except TemplateDoesNotExist:
        return render(request, 'register.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('users:user_login')

# ==============================================================================
# PROFILE MANAGEMENT
# ==============================================================================

@login_required
def user_profile(request):
    user = request.user
    experiences = Experience.objects.filter(user=user).order_by('-start_date')
    educations = Education.objects.filter(user=user).order_by('-end_date')
    skills = Skill.objects.filter(user=user)
    social_connections = SocialConnection.objects.filter(user=user)
    context = {
        'user': user,
        'experiences': experiences,
        'educations': educations,
        'skills': skills,
        'social_connections': social_connections,
        'total_referral_earnings': 0,
    }
    try:
        return render(request, 'users/profile.html', context)
    except TemplateDoesNotExist:
        return render(request, 'profile.html', context)

@login_required
def profile_edit(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('users:profile')
    else:
        form = ProfileEditForm(instance=user)
    try:
        return render(request, 'users/profile_edit.html', {'form': form})
    except TemplateDoesNotExist:
        return render(request, 'profile_edit.html', {'form': form})

# ==============================================================================
# AI CHAT & CONTEXT UTILITIES
# ==============================================================================

def _get_user_profile_data(user):
    """Gathers data to personalize AI responses."""
    return {
        "full_name": user.get_full_name() or user.username, 
        "bio": getattr(user, 'about', 'No bio provided'),
        "skills": [skill.name for skill in Skill.objects.filter(user=user)],
        "experiences": [
            f"{exp.title} at {exp.company_name}" 
            for exp in Experience.objects.filter(user=user)
        ]
    }

def _format_history_for_sdk(messages):
    """Formats history into strict alternating user/model turns."""
    formatted = []
    for msg in messages:
        role = "model" if msg.get("role", "").lower() in ["ai", "model", "assistant"] else "user"
        text = msg.get("text", "").strip()
        if not text:
            continue
            
        # Merge consecutive turns with the same role to avoid API errors
        if formatted and formatted[-1]["role"] == role:
            formatted[-1]["parts"][0]["text"] += f"\n{text}"
        else:
            formatted.append({"role": role, "parts": [{"text": text}]})
    return formatted

@csrf_exempt
@login_required
def gemini_proxy(request):
    """Handles AI chat using the official SDK (Dec 2025 Standard)."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)

    # API Key cleanup from Render Dashboard
    raw_api_key = os.environ.get("GEMINI_API_KEY", "").strip().replace('"', '').replace("'", "")
    if not raw_api_key:
        return JsonResponse({"error": "Server API Key is missing on Render."}, status=500)

    try:
        # Initialize official Client
        client = genai.Client(api_key=raw_api_key)
        
        data = json.loads(request.body)
        raw_contents = data.get('contents', [])
        
        # Build Profile Context as a System Instruction
        profile = _get_user_profile_data(request.user)
        system_instruction = (
            f"You are the Career Companion AI for Africana. "
            f"User: {profile['full_name']}. Bio: {profile['bio']}. "
            f"Skills: {', '.join(profile['skills'])}. History: {', '.join(profile['experiences'])}."
        )

        # Reformat history for the SDK
        history = _format_history_for_sdk(raw_contents)

        # Call the stable 2025 model: Gemini 2.0 Flash
        # Note: 'thinking_level' removed to satisfy SDK schema validation
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                max_output_tokens=1024,
            ),
            contents=history
        )

        if not response.text:
            return JsonResponse({"error": "AI returned empty response"}, status=500)

        return JsonResponse({"text": response.text})

    except Exception as e:
        print(f"DEBUG Gemini Exception: {str(e)}")
        return JsonResponse({"error": "AI Service Error", "details": str(e)}, status=400)

@login_required
def profile_ai(request):
    """Renders the Career Companion UI."""
    try:
        return render(request, 'users/profile_ai.html', {'user': request.user})
    except TemplateDoesNotExist:
        return render(request, 'profile_ai.html', {'user': request.user})

# Keep alias for backward compatibility
ai_quiz_generator = profile_ai