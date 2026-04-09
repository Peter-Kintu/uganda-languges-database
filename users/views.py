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
from django.db import IntegrityError
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
    return HttpResponse("google-site-verification: googlec0826a61eabee54e.html")

def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Sitemap: https://uganda-languges-database.onrender.com/sitemap.xml"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def tts_proxy(request):
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
            referrer_username = request.session.get('referrer')
            if referrer_username:
                try:
                    referrer_user = User.objects.get(username=referrer_username)
                    if hasattr(user, 'referrer'):
                        user.referrer = referrer_user
                except User.DoesNotExist:
                    pass 
            try:
                user.save()
            except IntegrityError as e:
                if 'username' in str(e).lower():
                    form.add_error('username', 'A user with that username already exists.')
                else:
                    form.add_error(None, 'Unable to complete registration. Please try again.')
            else:
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
        successful_referrals = Order.objects.filter(referrer=user, status='Completed')
        referral_earnings = successful_referrals.aggregate(Sum('total_commission'))['total_commission__sum'] or 0
    base_url = request.build_absolute_uri(reverse('users:user_register'))
    referral_link = f"{base_url}?ref={user.username}"
    context = {
        'user': user, 'experiences': experiences, 'educations': educations,
        'skills': skills, 'social_connections': social_connections,
        'referral_link': referral_link, 'successful_referrals': successful_referrals,
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
            return redirect('users:user_profile')
    else:
        form = ProfileEditForm(instance=user)
    try:
        return render(request, 'users/profile_edit.html', {'form': form})
    except TemplateDoesNotExist:
        return render(request, 'profile_edit.html', {'form': form})

# ==============================================================================
# AI CHAT LOGIC (Fixed for 2025 Standards)
# ==============================================================================

def _get_user_profile_data(user):
    """Retrieves detailed user context for personalization."""
    return {
        "full_name": user.get_full_name() or user.username, 
        "headline": getattr(user, 'headline', 'Professional'),
        "bio": getattr(user, 'about', 'No bio provided'),
        "skills": [skill.name for skill in Skill.objects.filter(user=user)],
        "experiences": [f"{exp.title} at {exp.company_name}" for exp in Experience.objects.filter(user=user)]
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
    """Proxies requests to Google Gemini for Africana AI with Search integration."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)

    api_key = os.environ.get("GEMINI_API_KEY", "").strip().replace('"', '').replace("'", "")
    if not api_key:
        return JsonResponse({"error": "API Key missing"}, status=500)

    try:
        client = genai.Client(api_key=api_key)
        data = json.loads(request.body)
        raw_contents = data.get('contents', [])
        
        # Pull profile data for personalization
        profile = _get_user_profile_data(request.user)
        
        # SYSTEM INSTRUCTION: Branding and Personalized context
        system_instruction = (
            f"You are Africana AI, the premier Career & Business Companion developed by Mwene Groups of Companies Limited. "
            f"You are speaking with {profile['full_name']}, a {profile['headline']}. "
            f"User Expertise: {', '.join(profile['skills'][:10])}. "
            "\n\nPERSONALIZATION RULE:"
            f"Address the user by name ({profile['full_name']}) occasionally. Tailor all career, business, and tech "
            f"advice to fit their specific role as a {profile['headline']} and their skills in {', '.join(profile['skills'][:3])}."
            "\n\nSEARCH LINK PROTOCOL:"
            "\nWhenever the user asks for jobs, specific products, media, or market info, you MUST provide "
            "Markdown links as actionable search buttons using these templates:"
            "\n- JOBS: [🔍 Search Jobs on Google](https://www.google.com/search?q=jobs+for+QUERY)"
            "\n- PRODUCTS: [🛒 Find on Amazon](https://www.amazon.com/s?k=QUERY) or [🛍️ Search Google Shopping](https://www.google.com/search?tbm=shop&q=QUERY)"
            "\n- MOVIES/MEDIA: [🎬 Watch on YouTube](https://www.youtube.com/results?search_query=QUERY+movie) or [📺 Search on Amazon Prime](https://www.amazon.com/s?k=QUERY+movie)"
            "\n- SELLING/MARKET: [📈 Research Market Prices](https://www.google.com/search?q=market+price+for+QUERY)"
            "\nAlways provide high-quality professional advice first, then the helpful links."
        )
        
        history = _format_history_for_sdk(raw_contents)

        models_to_try = [
            "gemini-2.0-flash", 
            "gemini-1.5-flash",
        ]
        
        last_err = ""
        for model_id in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_id, 
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                        max_output_tokens=1000,
                    ),
                    contents=history
                )
                if response.text:
                    return JsonResponse({"text": response.text, "model_used": model_id})
            except Exception as e:
                last_err = str(e)
                continue

        return JsonResponse({"error": f"AI unavailable. Last error: {last_err}"}, status=503)

    except Exception as global_e:
        return JsonResponse({"error": str(global_e)}, status=400)

@login_required
def profile_ai(request):
    try:
        return render(request, 'users/profile_ai.html', {'user': request.user})
    except TemplateDoesNotExist:
        return render(request, 'profile_ai.html', {'user': request.user})

ai_quiz_generator = profile_ai