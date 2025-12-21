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
    """Proxies TTS requests to avoid CORS issues with error handling."""
    text = request.GET.get('text', '')
    lang = request.GET.get('lang', 'en')
    if not text:
        return HttpResponse("No text provided", status=400)
    
    tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={text}&tl={lang}&client=tw-ob"
    try:
        response = requests.get(tts_url, stream=True, timeout=5)
        response.raise_for_status()
        return HttpResponse(response.content, content_type="audio/mpeg")
    except Exception as e:
        return JsonResponse({"error": "TTS Service Unavailable", "details": str(e)}, status=503)

# ==============================================================================
# AUTHENTICATION VIEWS
# ==============================================================================

def user_login(request):
    """
    Hardened login view to prevent 500 errors in production.
    Handles 'next' parameter from both GET and POST.
    """
    if request.user.is_authenticated:
        return redirect('languages:browse_job_listings')
    
    # Capture 'next' from either URL (GET) or form submission (POST)
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user() # Recommended over manual authenticate()
            if user:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                # Redirect to 'next' URL if safe, otherwise default to job listings
                return redirect(next_url if next_url else 'languages:browse_job_listings')
            else:
                messages.error(request, "Authentication failed.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
            
    context = {'form': form, 'next': next_url}
    
    # Try multiple paths to avoid TemplateDoesNotExist -> 500
    try:
        return render(request, 'users/login.html', context)
    except TemplateDoesNotExist:
        try:
            return render(request, 'login.html', context)
        except TemplateDoesNotExist:
            return HttpResponse("Login template not found. Check your directory structure.", status=500)

def user_register(request):
    """Handles user registration with robust validation error reporting."""
    if request.user.is_authenticated:
        return redirect('languages:browse_job_listings')
        
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful. Welcome!")
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
    """Logs the user out and redirects safely."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('users:user_login')

# ==============================================================================
# PROFILE & AI VIEWS
# ==============================================================================

@login_required
def user_profile(request):
    """Displays user profile with career data and safety fallbacks."""
    user = request.user
    context = {
        'user': user,
        'experiences': Experience.objects.filter(user=user).order_by('-start_date'),
        'educations': Education.objects.filter(user=user).order_by('-end_date'),
        'skills': Skill.objects.filter(user=user),
        'social_connections': SocialConnection.objects.filter(user=user),
        'total_referral_earnings': 0, 
    }
    
    try:
        return render(request, 'users/profile.html', context)
    except TemplateDoesNotExist:
        return render(request, 'profile.html', context)

@csrf_exempt
@login_required
def gemini_proxy(request):
    """Proxies requests to Gemini API with robust JSON error handling."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return JsonResponse({"error": "Server configuration error: Missing API Key."}, status=500)

        data = json.loads(request.body)
        contents = data.get('contents', [])
        
        profile_data = _get_user_profile_data(request.user)
        system_instruction = (
            "You are Career Companion AI. Help with CVs and interviews. "
            f"User Context: {json.dumps(profile_data)}. "
        )

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": _clean_history(contents),
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        resp = requests.post(url, json=payload, timeout=10)
        
        if resp.status_code != 200:
            return JsonResponse({"error": "AI Service unavailable", "details": resp.text}, status=resp.status_code)

        result = resp.json()
        # Safe extraction using .get() to prevent KeyErrors
        text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No response.')
        return JsonResponse({"text": text})

    except Exception as e:
        return JsonResponse({"error": "Internal Processing Error", "message": str(e)}, status=500)

def _get_user_profile_data(user):
    """Safely extracts profile data using getattr."""
    return {
        "username": user.username,
        "full_name": user.get_full_name() or user.username, 
        "location": getattr(user, 'location', 'Not provided'),
        "bio": getattr(user, 'about', 'Not provided'),
        "skills": [skill.name for skill in Skill.objects.filter(user=user)],
    }

def _clean_history(messages):
    """Standardizes chat history."""
    return [{"role": "model" if m.get("role") == "ai" else "user", "parts": [{"text": m.get("text", "")}]} for m in messages if m.get("text")]

@login_required
def profile_ai(request):
    """AI Career tools page with safety fallback."""
    try:
        return render(request, 'users/profile_ai.html', {'user': request.user})
    except TemplateDoesNotExist:
        return render(request, 'profile_ai.html', {'user': request.user})

ai_quiz_generator = profile_ai