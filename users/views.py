import os
import json
import logging
import requests
import time
import base64
from django.template.loader import render_to_string
from playwright.sync_api import sync_playwright
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse
from django.db import IntegrityError, models
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.template import TemplateDoesNotExist
from datetime import datetime


# Google auth token verification
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests


from google import genai
from google.genai import types
from google.genai.types import Content, GenerateContentConfig, Part

# Cerebras SDK imports
from cerebras.cloud.sdk import Cerebras

# Custom Forms and Models
from .models import CustomUser, Experience, Education, Skill, SocialConnection 
# Import cross-app models for profile aggregates (keep optional to avoid hard failures)
try:
    from hotel.models import Post, Like, Comment, Share, Connection
except Exception:
    Post = None
    Like = None
    Comment = None
    Share = None
    Connection = None
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
        f"Sitemap: https://{settings.DEFAULT_DOMAIN}/sitemap.xml"
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
        return redirect('hotel:social_feed')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url or reverse('hotel:social_feed')) 
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()


    google_client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    context = {
        'form': form,
        'next': request.GET.get('next', ''),
        'google_client_id': google_client_id,
    }

    try:
        return render(request, 'users/login.html', context)
    except TemplateDoesNotExist:
        return render(request, 'login.html', context)


@csrf_exempt
def google_auth_receiver(request):
    if request.method != 'POST':
        return HttpResponse('POST required', status=405)

    token = request.POST.get('credential')
    if not token:
        return HttpResponse('Missing credential', status=400)

    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if next_url:
        if next_url.startswith('/'):
            # relative URL, allow
            pass
        elif not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            next_url = ''

    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    if not client_id:
        return HttpResponse('Google client ID not configured', status=500)

    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
        if idinfo.get('iss') not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')

        email = idinfo.get('email')
        if not email:
            return HttpResponse('Email is required', status=400)

        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'first_name': first_name,
                'last_name': last_name,
            }
        )
        if created:
            user.save()

        login(request, user)
        return redirect(next_url or reverse('hotel:social_feed'))

    except ValueError as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Google auth ValueError: {str(e)}, client_id: {client_id[:10]}...")
        return HttpResponse('Invalid token', status=403)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Google auth error: {str(e)}")
        return HttpResponse(str(e), status=400)



def user_register(request):
    ref = request.GET.get('ref')
    if ref:
        request.session['referrer'] = ref
    if request.user.is_authenticated:
        return redirect('hotel:social_feed')
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
                return redirect('hotel:social_feed')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = CustomUserCreationForm()
    google_client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    context = {
        'form': form,
        'google_client_id': google_client_id,
        'next': request.GET.get('next', ''),
    }
    try:
        return render(request, 'users/register.html', context)
    except TemplateDoesNotExist:
        return render(request, 'register.html', context)

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
    # --- Profile aggregates ---
    # Connections / followers
    followers_count = 0
    following_count = 0
    connections_count = 0
    if Connection:
        followers_count = Connection.objects.filter(receiver=user, status='accepted').count()
        following_count = Connection.objects.filter(sender=user, status='accepted').count()
        connections_count = Connection.objects.filter(models.Q(sender=user) | models.Q(receiver=user), status='accepted').count()

    # Posts and engagements
    user_posts = []
    posts_count = 0
    impressions = None
    watch_hours = None
    try:
        if Post:
            user_posts = Post.objects.filter(author=user).order_by('-created_at')
            posts_count = user_posts.count()

            # If posts have explicit impression/watch fields, aggregate them, else compute a simple proxy
            if hasattr(Post, 'impressions'):
                impressions = user_posts.aggregate(Sum('impressions'))['impressions__sum'] or 0
            else:
                likes_count = Like.objects.filter(post__author=user).count() if Like else 0
                comments_count = Comment.objects.filter(post__author=user).count() if Comment else 0
                shares_count = Share.objects.filter(original_post__author=user).count() if Share else 0
                impressions = likes_count + comments_count + shares_count

            # Watch time aggregation if available on Post model
            if hasattr(Post, 'watch_seconds'):
                total_seconds = user_posts.aggregate(Sum('watch_seconds'))['watch_seconds__sum'] or 0
                watch_hours = round((total_seconds or 0) / 3600, 2)
    except Exception:
        # Be defensive: don't break profile rendering if any cross-app query fails
        user_posts = []
        posts_count = 0
        impressions = None
        watch_hours = None
    context = {
        'user': user, 'experiences': experiences, 'educations': educations,
        'skills': skills, 'social_connections': social_connections,
        'referral_link': referral_link, 'successful_referrals': successful_referrals,
        'total_referral_earnings': referral_earnings,
        'total_referral_count': successful_referrals.count() if Order else 0,
        'connections_count': connections_count,
        'followers_count': followers_count,
        'following_count': following_count,
        'user_posts': user_posts,
        'posts_count': posts_count,
        'impressions': impressions,
        'watch_hours': watch_hours,
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

@login_required
@csrf_exempt
def update_language(request):
    """Update user's preferred language"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            language = data.get('language', 'en')
            
            # Validate language code
            supported_languages = ['en', 'sw', 'lg', 'zu', 'xh', 'af', 'am', 'yo', 'ha', 'ar', 'fr', 'pt', 'es', 'de']
            if language not in supported_languages:
                language = 'en'
            
            request.user.language = language
            request.user.save()
            
            return JsonResponse({'success': True, 'language': language})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

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
        
        # SYSTEM INSTRUCTION: Branding and Personalized context (Shortened for token efficiency)
        system_instruction = (
            f"You are Africana AI, career companion by Mwene Groups. "
            f"User: {profile['full_name']}, {profile['headline']}. Skills: {', '.join(profile['skills'][:5])}. "
            "Provide highly actionable career and business advice for African professionals and entrepreneurs. Include specific next steps, resume tips, job search strategies, networking guidance, interview prep, and entrepreneurship planning. For searches: use Markdown links like [🔍 Search Jobs](https://google.com/search?q=jobs+QUERY)."
        )
        
        history = _format_history_for_sdk(raw_contents[-6:])  # Limit to last 3 exchanges for token efficiency

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

@csrf_exempt
@login_required
def cerebras_proxy(request):
    """Proxies chat requests to Cerebras using gpt-oss-120b and falls back to Sunbird AI on failure."""
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST requests are allowed"}, status=405)

    try:
        body = json.loads(request.body)
        raw_contents = body.get('contents', [])

        profile = _get_user_profile_data(request.user)
        default_instruction = (
            f"You are Africana AI, career companion by Mwene Groups. "
            f"User: {profile['full_name']}, {profile['headline']}. Skills: {', '.join(profile['skills'][:5])}. "
            "Provide highly actionable career and business advice for African professionals and entrepreneurs. Include specific next steps, resume tips, job search strategies, networking guidance, interview prep, and entrepreneurship planning. For searches: use Markdown links like [🔍 Search Jobs](https://google.com/search?q=jobs+QUERY)."
        )
        system_instruction = body.get('system_instruction') or default_instruction

        messages = [{"role": "system", "content": system_instruction}]
        for msg in raw_contents[-6:]:
            role = "assistant" if msg.get("role", "").lower() in ["ai", "model", "assistant"] else "user"
            text = msg.get("text", "").strip()
            if text:
                messages.append({"role": role, "content": text})

        # --- ATTEMPT PRIMARY CALL (Cerebras - gpt-oss-120b) ---
        try:
            api_key = os.environ.get("CEREBRAS_API_KEY", "").strip().replace('"', '').replace("'", "")
            if not api_key:
                raise ValueError("Cerebras API key is missing.")

            client = Cerebras(api_key=api_key)
            completion = client.chat.completions.create(
                messages=messages,
                model="gpt-oss-120b",
                max_completion_tokens=1024,
                temperature=0.7,
                top_p=1,
                stream=False,
            )

            response_text = completion.choices[0].message.content if completion.choices else ""
            if response_text:
                return JsonResponse({
                    "text": response_text,
                    "model_used": "gpt-oss-120b (Primary)"
                })

            raise Exception("Empty response received from Cerebras endpoint.")

        except Exception as primary_error:
            logging.warning(f"Primary AI model failed/limited: {str(primary_error)}. Attempting Sunbird AI fallback...")

            sunbird_token = os.environ.get("SUNBIRD_API_KEY", "").strip().replace('"', '').replace("'", "")
            if not sunbird_token:
                return JsonResponse({
                    "error": "Primary API failed and Sunbird AI fallback credentials are not configured."
                }, status=503)

            sunbird_url = "https://api.sunbird.ai/tasks/sunflower_inference"
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {sunbird_token}",
                "Content-Type": "application/json",
            }
            payload = {"messages": messages}

            sunbird_response = requests.post(sunbird_url, headers=headers, json=payload, timeout=15)
            if sunbird_response.status_code == 200:
                sunbird_data = sunbird_response.json()
                fallback_text = sunbird_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if fallback_text:
                    return JsonResponse({
                        "text": fallback_text,
                        "model_used": "Sunbird AI (Fallback)"
                    })

            return JsonResponse({
                "error": "Service temporarily unavailable. Both primary and fallback endpoints failed.",
                "details": sunbird_response.text if 'sunbird_response' in locals() else str(primary_error)
            }, status=503)

    except json.JSONDecodeError as e:
        return JsonResponse({"error": f"Invalid JSON format: {str(e)}"}, status=400)
    except Exception as e:
        logging.error(f"Unexpected proxy view exception: {str(e)}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)

ai_quiz_generator = profile_ai


@csrf_exempt
@login_required
def generate_advert_image(request):
    """Generates an advertisement graphic using Sunbird AI's Image Generation API."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)

    sunbird_token = os.environ.get("SUNBIRD_API_KEY", "").strip().replace('"', '').replace("'", "")
    if not sunbird_token:
        return JsonResponse({"error": "Sunbird API key configuration missing."}, status=500)

    try:
        data = json.loads(request.body)
        user_prompt = data.get('prompt', '').strip()

        if not user_prompt:
            return JsonResponse({"error": "Please provide a description for the advertisement image."}, status=400)

        # Optimize prompt styling automatically for sleek African e-commerce/tech products
        enhanced_prompt = (
            f"Professional product marketing commercial photograph, studio lighting, crisp clean focus, "
            f"vibrant modern aesthetic, tailored for an African digital business landscape: {user_prompt}"
        )

        # Target Sunbird's text-to-image pipeline
        sunbird_url = "https://api.sunbird.ai/tasks/text_to_image"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {sunbird_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": enhanced_prompt
        }

        response = requests.post(sunbird_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            response_data = response.json()
            # Sunbird provides a hosted URL or a base64 string depending on their task configuration. 
            # If they return a direct image URL under 'image_url' or 'url':
            image_url = response_data.get("image_url") or response_data.get("url")
            
            # Fallback check if it returns raw base64 data instead
            if not image_url and "base64" in response_data:
                image_url = f"data:image/jpeg;base64,{response_data['base64']}"

            if image_url:
                return JsonResponse({
                    "success": True,
                    "image_url": image_url,
                    "prompt_used": user_prompt
                })
            
            return JsonResponse({"error": "Sunbird processed the request but did not return a valid graphic string."}, status=502)
        else:
            return JsonResponse({"error": f"Sunbird Image API error: {response.text}"}, status=response.status_code)

    except Exception as e:
        logging.error(f"Sunbird Image Generation Exception: {str(e)}", exc_info=True)
        return JsonResponse({"error": f"Internal image pipeline error: {str(e)}"}, status=500)



@csrf_exempt
@login_required
def generate_document_pdf(request):
    """
    Accepts text markdown or raw data from Africana AI, transforms it into an 
    excellently styled document structure, and renders it directly into a PDF download.
    """
    if request.method == 'POST':
        # Step A: Capture data from the AI chat session
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid request content format."}, status=400)
            
        text_content = data.get('text', '').strip()
        doc_type = data.get('doc_type', 'document') # 'resume' or 'business_plan'
        
        if not text_content:
            return JsonResponse({"error": "No document data provided to compile."}, status=400)
            
        # Temporarily cache data in the user's session to allow immediate safe retrieval via GET download
        request.session['pending_pdf_text'] = text_content
        request.session['pending_pdf_type'] = doc_type
        
        # Return link routing target
        return JsonResponse({
            "success": True, 
            "redirect_url": reverse('users:generate_document_pdf')
        })

    # Step B: When the download route is requested via a GET request
    text_content = request.session.get('pending_pdf_text', '')
    doc_type = request.session.get('pending_pdf_type', 'document')

    if not text_content:
        return redirect('users:profile_ai')

    # If the user clicks the final download action link
    if request.GET.get('download') == '1':
        # Convert plain line-breaks to printable semantic elements safely
        formatted_html_content = text_content.replace('\n', '<br>').replace('**', '<b>').replace('</b><b>', '')

        # Apply strict professional CSS design guidelines tailored strictly for paper margins
        accent_color = "#16a34a" if doc_type == "resume" else "#0f172a" # Green for resumes, deep corporate blue for plans

        html_string = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    color: #1e293b;
                    line-height: 1.6;
                    font-size: 10.5pt;
                    margin: 0;
                    padding: 20mm 15mm;
                }}
                h1 {{ color: {accent_color}; }}
                .content-wrapper {{ max-width: 800px; margin: 0 auto; }}
            </style>
        </head>
        <body>
            <div class="content-wrapper">
                {formatted_html_content}
            </div>
        </body>
        </html>
        """

        # Use Playwright (Chromium) to render HTML to PDF for robust cloud builds
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.set_content(html_string, wait_until='networkidle')
                pdf_bytes = page.pdf(format='A4', margin={'top':'20mm','bottom':'20mm','left':'15mm','right':'15mm'})
                browser.close()

            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="africana_{doc_type}_{int(time.time())}.pdf"'

            # Clean up session space safely after download
            del request.session['pending_pdf_text']
            del request.session['pending_pdf_type']

            return response
        except Exception as e:
            logging.error(f"Playwright PDF generation failed: {str(e)}", exc_info=True)
            return HttpResponse("PDF rendering failed on server.", status=500)

    # Render intermediate loading display before auto-download execution sets up
    return render(request, 'users/download_pdf.html', {'doc_type': doc_type})