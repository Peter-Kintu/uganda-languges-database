import os
import json
import requests
import time
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
    from eshop.models import Product, CartItem, Order 
except ImportError:
    Product = None
    CartItem = None
    Order = None

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
# AUTHENTICATION VIEWS (With Referral Capture)
# ==============================================================================

def user_login(request):
    # Capture referral if present in the login URL
    ref = request.GET.get('ref')
    if ref:
        request.session['referrer'] = ref

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
    ref = request.GET.get('ref')
    if ref:
        request.session['referrer'] = ref

    if request.user.is_authenticated:
        return redirect('languages:browse_job_listings')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            
            # FIX: Use 'referrer' instead of 'referred_by'
            referrer_username = request.session.get('referrer')
            if referrer_username:
                try:
                    referrer_user = User.objects.get(username=referrer_username)
                    # Check if your CustomUser model has a 'referrer' field
                    # If it's a field on the User model, set it here:
                    if hasattr(user, 'referrer'):
                        user.referrer = referrer_user
                except User.DoesNotExist:
                    pass 
            
            user.save()
            login(request, user)
            
            if 'referrer' in request.session:
                del request.session['referrer']
                
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
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('users:user_login')

# ==============================================================================
# PROFILE & REFERRAL DASHBOARD
# ==============================================================================

@login_required
def user_profile(request):
    user = request.user
    experiences = Experience.objects.filter(user=user).order_by('-start_date')
    educations = Education.objects.filter(user=user).order_by('-end_date')
    skills = Skill.objects.filter(user=user)
    social_connections = SocialConnection.objects.filter(user=user)
    
    successful_referrals = []
    referral_earnings = 0
    
    if Order:
        # FIX: Changed 'referred_by' to 'referrer'
        # Also, check if your Order model links to User object or Username string
        # If Order.referrer is a ForeignKey to User:
        successful_referrals = Order.objects.filter(referrer=user, status='Completed')
        
        # Calculate Earnings using the total_commission sum
        referral_earnings = successful_referrals.aggregate(Sum('total_commission'))['total_commission__sum'] or 0
    
    base_url = request.build_absolute_uri(reverse('users:user_register'))
    referral_link = f"{base_url}?ref={user.username}"

    context = {
        'user': user,
        'experiences': experiences,
        'educations': educations,
        'skills': skills,
        'social_connections': social_connections,
        'referral_link': referral_link,
        'successful_referrals': successful_referrals,
        'total_referral_earnings': referral_earnings,
        'total_referral_count': successful_referrals.count() if Order else 0,
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
            return redirect('users:user_profile') # Fixed redirect name
    else:
        form = ProfileEditForm(instance=user)
    try:
        return render(request, 'users/profile_edit.html', {'form': form})
    except TemplateDoesNotExist:
        return render(request, 'profile_edit.html', {'form': form})

# ==============================================================================
# AI CHAT & CONTEXT UTILITIES (Keep your existing Gemini logic)
# ==============================================================================

def _get_user_profile_data(user):
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
    formatted = []
    for msg in messages:
        role = "model" if msg.get("role", "").lower() in ["ai", "model", "assistant"] else "user"
        text = msg.get("text", "").strip()
        if not text: continue
            
        if formatted and formatted[-1]["role"] == role:
            formatted[-1]["parts"][0]["text"] += f"\n{text}"
        else:
            formatted.append({"role": role, "parts": [{"text": text}]})
    return formatted

@csrf_exempt
@login_required
def gemini_proxy(request):
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)

    raw_api_key = os.environ.get("GEMINI_API_KEY", "").strip().replace('"', '').replace("'", "")
    if not raw_api_key:
        return JsonResponse({"error": "API Key missing"}, status=500)

    try:
        client = genai.Client(api_key=raw_api_key)
        data = json.loads(request.body)
        raw_contents = data.get('contents', [])
        
        profile = _get_user_profile_data(request.user)
        system_instruction = (
            f"You are the Career Companion AI for Africana. "
            f"User: {profile['full_name']}. Bio: {profile['bio']}. "
            f"Skills: {', '.join(profile['skills'])}. History: {', '.join(profile['experiences'])}."
        )
        history = _format_history_for_sdk(raw_contents)

        models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash"]
        
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name, 
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                        max_output_tokens=1024,
                    ),
                    contents=history
                )
                if response.text:
                    return JsonResponse({"text": response.text, "model_used": model_name})
            except Exception as model_e:
                if any(x in str(model_e) for x in ["429", "404", "RESOURCE_EXHAUSTED"]):
                    continue
                raise model_e 

        return JsonResponse({"error": "Quota Exceeded"}, status=429)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@login_required
def profile_ai(request):
    try:
        return render(request, 'users/profile_ai.html', {'user': request.user})
    except TemplateDoesNotExist:
        return render(request, 'profile_ai.html', {'user': request.user})

ai_quiz_generator = profile_ai