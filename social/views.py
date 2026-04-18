import os
import json
import random
import uuid
import urllib.parse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.db.models import F, Q
from django.urls import reverse

# Internal App Models and Forms
from .models import BusinessReel, SocialProfile, SecureMessage
from .forms import BusinessReelUploadForm, SecureMessageForm
# External User Model from users app
from users.models import CustomUser

class FeedView(ListView):
    """
    Pillar 2: Main social feed displaying Business Reels.
    Optimized for high-speed performance on mobile networks.
    """
    model = BusinessReel
    template_name = 'social/feed.html'
    context_object_name = 'reels'
    
    def get_queryset(self):
        # Optimized with select_related to avoid N+1 queries on profile data
        return BusinessReel.objects.filter(is_active=True).select_related(
            'author', 
            'author__social_profile'
        ).order_by('-created_at')

class BentoProfileView(DetailView):
    """
    Pillar 4: Modern Bento-style profile view.
    Highlights Trust Ledger and Proof of Work.
    """
    model = CustomUser
    template_name = 'social/bento_profile.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Safe access to social profile via the signal-backed relation
        context['social'] = getattr(self.object, 'social_profile', None)
        context['user_reels'] = BusinessReel.objects.filter(author=self.object, is_active=True)
        
        # Fetch verified video endorsements (Proof of Work)
        if hasattr(self.object, 'received_endorsements'):
            context['endorsements'] = self.object.received_endorsements.filter(
                is_verified_transaction=True
            ).order_by('-created_at')[:5]
        return context

@login_required
def upload_reel(request):
    """
    Pillar 2 & 3: Africa-First Upload Flow.
    UPDATED: Now captures and saves WhatsApp number to the SocialProfile.
    """
    if request.method == 'POST':
        form = BusinessReelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            reel = form.save(commit=False)
            reel.author = request.user
            
            # Generate unique share token for viral loop metrics
            if not hasattr(reel, 'share_token') or not reel.share_token:
                reel.share_token = uuid.uuid4().hex[:12]
            reel.save()

            # --- WHATSAPP UPDATE LOGIC ---
            whatsapp = form.cleaned_data.get('whatsapp_number')
            if whatsapp:
                profile, created = SocialProfile.objects.get_or_create(user=request.user)
                profile.whatsapp_number = whatsapp
                profile.save()
            
            messages.success(request, "Deployment Successful: Your reel is live.")
            return redirect('social:social_feed')
    else:
        # Pre-fill WhatsApp number if it already exists in the profile
        initial_data = {}
        if hasattr(request.user, 'social_profile'):
            initial_data['whatsapp_number'] = request.user.social_profile.whatsapp_number
        form = BusinessReelUploadForm(initial=initial_data)

    return render(request, 'social/upload.html', {'form': form})

# --- INTERACTION PROTOCOLS ---

@login_required
@require_POST
def toggle_like_reel(request, reel_id):
    """
    Social Proof: Toggles a like on a reel via AJAX.
    UPDATED: Now triggers author trust score recalculation and returns verification status.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    if request.user in reel.likes.all():
        reel.likes.remove(request.user)
        liked = False
    else:
        reel.likes.add(request.user)
        liked = True
    
    # --- TRUST SCORE INCREASE BASED ON LIKES ---
    if liked and reel.likes.count() % 5 == 0:
        if hasattr(reel.author, 'social_profile'):
            profile = reel.author.social_profile
            profile.trust_score = min(100.0, profile.trust_score + 1.0)
            profile.save(update_fields=['trust_score'])
    
    # --- TRIGGER TRUST SCORE UPDATE & CRYPTOGRAPHIC SEAL ---
    is_verified = False
    new_trust_score = 0
    
    if hasattr(reel.author, 'social_profile'):
        profile = reel.author.social_profile
        # Atomic update of Trust Ledger (Pillar 1)
        profile.update_trust_score() 
        new_trust_score = profile.trust_score
        is_verified = getattr(profile, 'is_trust_verified', False) 
    
    return JsonResponse({
        'status': 'success',
        'liked': liked,
        'total_likes': reel.likes.count(),
        'new_trust_score': new_trust_score,
        'is_verified': is_verified
    })

@csrf_exempt
@require_POST
def track_share(request, reel_id):
    """
    Branding: Increments the share count (Viral Loop metric).
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    reel.share_count = F('share_count') + 1
    reel.save(update_fields=['share_count'])
    reel.refresh_from_db()
    
    return JsonResponse({
        'status': 'SUCCESS',
        'total_shares': reel.share_count
    })

@csrf_exempt
@require_POST
def track_download(request, reel_id):
    """
    Performance: Increments download count (Offline utility metric).
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    reel.download_count = F('download_count') + 1
    reel.save(update_fields=['download_count'])
    reel.refresh_from_db()
    
    return JsonResponse({
        'status': 'SUCCESS',
        'total_downloads': reel.download_count
    })

@login_required
@require_POST
def add_comment(request, reel_id):
    """
    Adds a comment to a reel.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    content = request.POST.get('content')
    if content:
        Comment.objects.create(reel=reel, author=request.user, content=content)
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def toggle_comment_like(request, comment_id):
    """
    Toggles like on a comment.
    """
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user in comment.likes.all():
        comment.likes.remove(request.user)
        liked = False
    else:
        comment.likes.add(request.user)
        liked = True
    return JsonResponse({'status': 'success', 'liked': liked, 'total_likes': comment.likes.count()})

@login_required
def translate_comment(request, comment_id):
    """
    Translates a comment.
    """
    comment = get_object_or_404(Comment, id=comment_id)
    target_lang = request.GET.get('lang', 'en')
    translated = translate_text(comment.content, target_language=target_lang)
    return JsonResponse({'translated': translated})

@login_required
def translate_reel_caption(request, reel_id):
    """
    Translates a reel caption.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    target_lang = request.GET.get('lang', 'en')
    translated = translate_text(reel.caption, target_language=target_lang)
    return JsonResponse({'translated': translated})

@login_required
@require_POST
def toggle_follow(request, user_id):
    """
    Toggles follow on a user.
    """
    user = get_object_or_404(CustomUser, id=user_id)
    if request.user in user.followers.all():
        user.followers.remove(request.user)
        followed = False
    else:
        user.followers.add(request.user)
        followed = True
    return JsonResponse({'status': 'success', 'followed': followed})

@login_required
@require_POST
def create_story(request):
    """
    Creates a story.
    """
    # Assuming story creation logic
    return JsonResponse({'status': 'success'})

@login_required
def stories_feed(request):
    """
    Stories feed.
    """
    stories = Story.objects.all()
    return render(request, 'social/stories.html', {'stories': stories})

@login_required
def view_story(request, story_id):
    """
    View a story.
    """
    story = get_object_or_404(Story, id=story_id)
    return render(request, 'social/story_detail.html', {'story': story})

# --- SOVEREIGN MESSAGING PROTOCOLS ---

@login_required
def inbox(request):
    """
    Pillar 4: Inbox view to see all ongoing conversations.
    """
    sent_ids = SecureMessage.objects.filter(sender=request.user).values_list('recipient', flat=True)
    received_ids = SecureMessage.objects.filter(recipient=request.user).values_list('sender', flat=True)
    
    partner_ids = set(list(sent_ids) + list(received_ids))
    chat_partners = CustomUser.objects.filter(id__in=partner_ids)
    
    return render(request, 'social/inbox.html', {'chat_partners': chat_partners})

@login_required
def chat_detail(request, partner_id):
    """
    Pillar 4: The Chat Thread between sender and receiver.
    """
    partner = get_object_or_404(CustomUser, id=partner_id)
    
    thread = SecureMessage.objects.filter(
        (Q(sender=request.user) & Q(recipient=partner)) |
        (Q(sender=partner) & Q(recipient=request.user))
    ).order_by('timestamp')
    
    # Mark messages as read upon entering thread
    thread.filter(recipient=request.user, is_read=False).update(is_read=True)

    if request.method == "POST":
        content = request.POST.get('content')
        if content:
            SecureMessage.objects.create(
                sender=request.user,
                recipient=partner,
                content=content
            )
            return redirect('social:chat_detail', partner_id=partner.id)

    return render(request, 'social/chat_detail.html', {
        'partner': partner,
        'thread': thread
    })

@login_required
@require_POST
def initiate_hire_protocol(request, reel_id):
    """
    Handles the "Secure Handshake" / Hire Me protocol.
    UPDATED: Now includes WhatsApp redirection data if the creator has a number linked.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    creator_profile = getattr(reel.author, 'social_profile', None)
    
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            content = data.get('content')
        except json.JSONDecodeError:
            content = None
    else:
        content = request.POST.get('content')
    
    if content:
        # Create internal record for logs and trust score building
        SecureMessage.objects.create(
            sender=request.user,
            recipient=reel.author,
            related_reel=reel,
            content=content
        )
        
        # Check if we should redirect to WhatsApp for the deal closure
        whatsapp_number = getattr(creator_profile, 'whatsapp_number', None)
        
        if whatsapp_number:
            encoded_msg = urllib.parse.quote(content)
            wa_url = f"https://wa.me/{whatsapp_number}?text={encoded_msg}"
            
            return JsonResponse({
                'status': 'SENT', 
                'message': 'Handshake Logged. Redirecting to WhatsApp...',
                'redirect_url': wa_url,
                'is_whatsapp': True
            })

        # Fallback to internal chat
        chat_url = reverse('social:chat_detail', kwargs={'partner_id': reel.author.id})
        return JsonResponse({
            'status': 'SENT', 
            'message': 'Handshake Established internally.',
            'redirect_url': chat_url,
            'is_whatsapp': False
        })
    
    return JsonResponse({'status': 'ERROR', 'message': 'Handshake Failed: Empty Content.'}, status=400)

@login_required
def ai_negotiate_price(request, reel_id):
    """
    Pillar 3: The "Haggle" Protocol.
    Agentic negotiation floor logic.
    """
    if request.method == "POST":
        reel = get_object_or_404(BusinessReel, id=reel_id, is_active=True)
        
        if not reel.price:
            return JsonResponse({
                'status': 'INFO', 
                'message': 'Professional showcase mode. Use "Hire" for custom rates.'
            })
        
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            buyer_offer = float(data.get('offer', 0))
            
            floor_price = float(getattr(reel, 'floor_price', reel.price * 0.8))
            public_price = float(reel.price)
            
            if buyer_offer >= public_price:
                return JsonResponse({
                    'status': 'SUCCESS', 
                    'message': 'Offer accepted immediately.',
                    'price': buyer_offer
                })

            if buyer_offer >= floor_price:
                # If offer is within 5% of public price, accept automatically
                if (public_price - buyer_offer) / public_price <= 0.05:
                     return JsonResponse({
                        'status': 'SUCCESS', 
                        'message': 'Agent authorized this deal!',
                        'price': buyer_offer
                    })
                
                suggested_midpoint = (public_price + buyer_offer) / 2
                return JsonResponse({
                    'status': 'COUNTER',
                    'message': 'Agent proposes middle ground:',
                    'price': round(suggested_midpoint, 2)
                })
            
            # Offer is too low, counter with floor + small margin
            counter_offer = max(floor_price * 1.05, buyer_offer * 1.10) 
            counter_offer = min(counter_offer, public_price)
            
            return JsonResponse({
                'status': 'COUNTER', 
                'message': 'Best possible deal from the Agent:',
                'price': round(counter_offer, 2)
            })
            
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({'status': 'ERROR', 'message': 'Data Handshake Error.'}, status=400)
            
    return JsonResponse({'status': 'ERROR', 'message': 'Protocol Violation.'}, status=405)

@login_required
def negotiation_page(request, reel_id):
    """
    Page for AI-powered price negotiation with a reel.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id, is_active=True)
    
    if not reel.price:
        messages.error(request, "This item is not for sale.")
        return redirect('social:social_feed')
    
    context = {
        'reel': reel,
        'floor_price': getattr(reel, 'floor_price', reel.price * 0.8),
        'currency': reel.currency,
    }
    return render(request, 'social/negotiation.html', context)