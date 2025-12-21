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
import json
import os
import requests

# Import the Custom Forms and Models
from .models import CustomUser, Experience, Education, Skill, SocialConnection 
from .forms import CustomUserCreationForm, ProfileEditForm
from django.contrib.auth import get_user_model

User = get_user_model()

# Safely import eshop models to prevent crashes if the app is not fully linked
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
        "Sitemap: https://initial-danette-africana-60541726.koyeb.app/sitemap.xml"
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
    """Handles user login with robust redirects and template fallbacks."""
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
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
            
    context = {'form': form, 'next': request.GET.get('next', '')}
    try:
        return render(request, 'users/login.html', context)
    except TemplateDoesNotExist:
        return render(request, 'login.html', context)

def user_register(request):
    """Handles user registration and automatically logs them in."""
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
# PROFILE & REFERRAL VIEWS
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
    """Gathers profile data for AI context."""
    return {
        "full_name": user.get_full_name() or user.username, 
        "location": getattr(user, 'location', 'Not provided'),
        "bio": getattr(user, 'about', 'Not provided'),
        "skills": [skill.name for skill in Skill.objects.filter(user=user)],
        "experiences": [
            {"title": getattr(exp, 'title', 'Employee'), "company": getattr(exp, 'company_name', 'Not specified')}
            for exp in Experience.objects.filter(user=user)
        ]
    }

def _clean_history(messages):
    """Standardizes chat history for Gemini (must alternate user/model)."""
    cleaned = []
    last_role = None
    for msg in messages:
        role = "model" if msg.get("role", "").lower() in ["ai", "model", "assistant"] else "user"
        text = msg.get("text")
        if not text: continue
        
        if role == last_role:
            if cleaned:
                cleaned[-1]["parts"][0]["text"] += f"\n{text}"
                continue
        
        cleaned.append({"role": role, "parts": [{"text": text}]})
        last_role = role
    return cleaned

@csrf_exempt
@login_required
def gemini_proxy(request):
    """Proxies chat requests to Gemini with stable v1 API."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)

    # 1. API Key Cleaning
    raw_key = os.environ.get("GEMINI_API_KEY", "")
    api_key = raw_key.strip().replace('"', '').replace("'", "")

    if not api_key:
        return JsonResponse({"error": "API Key missing from server."}, status=500)

    try:
        data = json.loads(request.body)
        contents = data.get('contents', [])

        # 2. Build Context
        profile = _get_user_profile_data(request.user)
        profile_summary = (
            f"User: {profile['full_name']}. Bio: {profile['bio']}. "
            f"Skills: {', '.join(profile['skills'])}."
        )

        # 3. Payload with stable v1 endpoint
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": _clean_history(contents),
            "system_instruction": {
                "parts": [{"text": f"You are Career Companion AI for Africana. Context: {profile_summary}"}]
            },
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
        }

        resp = requests.post(url, json=payload, timeout=15)
        
        if resp.status_code != 200:
            print(f"DEBUG: Google API Error: {resp.text}")
            return JsonResponse(resp.json(), status=resp.status_code)

        result = resp.json()
        text = result['candidates'][0]['content']['parts'][0]['text']
        return JsonResponse({"text": text})

    except Exception as e:
        print(f"DEBUG: Proxy Exception: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def profile_ai(request):
    """Renders the AI tools page."""
    try:
        return render(request, 'users/profile_ai.html', {'user': request.user})
    except TemplateDoesNotExist:
        return render(request, 'profile_ai.html', {'user': request.user})

ai_quiz_generator = profile_ai