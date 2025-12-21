from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
import json
import os
import requests

# Import the Custom Forms and Models
from .forms import CustomUserCreationForm, ProfileEditForm
from .models import CustomUser, Experience, Education, Skill, SocialConnection 

# Assuming referral logic relates to Product commissions in eshop
from eshop.models import Product, CartItem 

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
        "allow:",
        "Sitemap: https://initial-danette-africana-60541726.koyeb.app/sitemap.xml"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def tts_proxy(request):
    """
    REQUIRED FIX: Proxies TTS requests to avoid CORS issues.
    This resolves the ImportError in your urls.py.
    """
    text = request.GET.get('text', '')
    lang = request.GET.get('lang', 'en')
    if not text:
        return HttpResponse("No text provided", status=400)
    
    tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={text}&tl={lang}&client=tw-ob"
    try:
        response = requests.get(tts_url, stream=True)
        return HttpResponse(response.content, content_type="audio/mpeg")
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

# ==============================================================================
# AUTHENTICATION VIEWS
# ==============================================================================

def user_login(request):
    """Handles user login and redirects to the job listings page."""
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
                return redirect(request.POST.get('next') or reverse('languages:browse_job_listings')) 
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid form submission.")
            
    form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})

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
        
    return render(request, 'users/register.html', {'form': form})

@login_required
def user_logout(request):
    """Logs the user out and redirects to the login page."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('users:user_login')

# ==============================================================================
# PROFILE & REFERRAL VIEWS
# ==============================================================================

@login_required
def user_profile(request):
    """Displays user profile with career data and Referral Earnings."""
    user = request.user
    
    experiences = Experience.objects.filter(user=user).order_by('-start_date')
    educations = Education.objects.filter(user=user).order_by('-start_date')
    skills = Skill.objects.filter(user=user)
    social_connections = SocialConnection.objects.filter(user=user)

    # Referral Earnings Calculation
    # Note: This logic assumes you will eventually have a 'ReferralReward' model.
    # For now, we initialize it to 0 as a placeholder for the template.
    total_referral_earnings = 0 

    context = {
        'user': user,
        'experiences': experiences,
        'educations': educations,
        'skills': skills,
        'social_connections': social_connections,
        'total_referral_earnings': total_referral_earnings,
    }
    return render(request, 'users/profile.html', context)

@login_required
def profile_edit(request):
    """Handles editing user profile information."""
    user = request.user
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('users:profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = ProfileEditForm(instance=user)
        
    return render(request, 'users/profile_edit.html', {'form': form})

# ==============================================================================
# AI CHAT & CONTEXT UTILITIES
# ==============================================================================

def _get_user_profile_data(user):
    """Gathers profile and referral data for the AI context."""
    return {
        "username": user.username,
        "full_name": user.get_full_name() or user.username, 
        "location": getattr(user, 'location', 'Not provided'),
        "bio": getattr(user, 'bio', 'Not provided'),
        "skills": [skill.name for skill in Skill.objects.filter(user=user)],
        "referral_summary": {
            "referral_link": f"https://africana.market/?ref={user.username}"
        },
        "experiences": [
            {"title": exp.job_title, "company": exp.company}
            for exp in Experience.objects.filter(user=user)
        ]
    }

def _clean_history(messages):
    """Standardizes chat history for the Gemini API format."""
    cleaned = []
    for msg in messages:
        role = "model" if msg.get("role", "").lower() == "ai" else "user"
        text_content = msg.get("text")
        if not text_content: continue
        
        cleaned.append({
            "role": role,
            "parts": [{"text": text_content}]
        })
    return cleaned



@csrf_exempt
@login_required
def gemini_proxy(request):
    """Proxies chat requests to Gemini with integrated User & Referral context."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        data = json.loads(request.body)
        contents = data.get('contents', [])
        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            return JsonResponse({"error": "API Key missing."}, status=500)

        profile_json = json.dumps(_get_user_profile_data(request.user))
        system_instruction = (
            "You are Career Companion AI. You help with CVs and career strategy. "
            f"User Context: {profile_json}. "
            "If asked about referrals, explain that they earn commissions by sharing links."
        )

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": _clean_history(contents),
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        resp = requests.post(url, json=payload)
        
        if resp.status_code != 200:
            return JsonResponse({"error": "AI Error"}, status=resp.status_code)

        result = resp.json()
        text = result['candidates'][0]['content']['parts'][0]['text']
        return JsonResponse({"text": text})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def profile_ai(request):
    """Renders the AI Career tools page."""
    return render(request, 'users/profile_ai.html', {'user': request.user})