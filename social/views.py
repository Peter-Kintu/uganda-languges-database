import os
import json
import random
import uuid
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
            )[:5]
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
    UPDATED: Now triggers author trust score recalculation (5% per like).
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    if request.user in reel.likes.all():
        reel.likes.remove(request.user)
        liked = False
    else:
        reel.likes.add(request.user)
        liked = True
    
    # --- TRIGGER TRUST SCORE UPDATE ---
    # Update the author's score immediately so the 5% per like is reflected
    if hasattr(reel.author, 'social_profile'):
        reel.author.social_profile.update_trust_score()
    
    return JsonResponse({
        'status': 'success',
        'liked': liked,
        'total_likes': reel.likes.count(),
        'new_trust_score': reel.author.social_profile.trust_score
    })

@csrf_exempt
@require_POST
def track_share(request, reel_id):
    """
    Branding: Increments the share count and returns new total for front-end display.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    reel.share_count = F('share_count') + 1
    reel.save()
    reel.refresh_from_db()
    
    return JsonResponse({
        'status': 'SUCCESS',
        'total_shares': reel.share_count
    })

@csrf_exempt
@require_POST
def track_download(request, reel_id):
    """
    Performance: Increments download count and returns new total for front-end display.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    reel.download_count = F('download_count') + 1
    reel.save()
    reel.refresh_from_db()
    
    return JsonResponse({
        'status': 'SUCCESS',
        'total_downloads': reel.download_count
    })

# --- SOVEREIGN MESSAGING PROTOCOLS (WHATSAPP STYLE) ---

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
    Handles the "Secure Handshake".
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
        # Create internal record for logs/trust score
        SecureMessage.objects.create(
            sender=request.user,
            recipient=reel.author,
            related_reel=reel,
            content=content
        )
        
        # Check if we should redirect to WhatsApp
        whatsapp_number = getattr(creator_profile, 'whatsapp_number', None)
        
        if whatsapp_number:
            # Construct WhatsApp link with the user's message
            import urllib.parse
            encoded_msg = urllib.parse.quote(content)
            wa_url = f"https://wa.me/{whatsapp_number}?text={encoded_msg}"
            
            return JsonResponse({
                'status': 'SENT', 
                'message': 'Redirecting to WhatsApp...',
                'redirect_url': wa_url,
                'is_whatsapp': True
            })

        # Fallback to internal chat if no WhatsApp number is set
        chat_url = reverse('social:chat_detail', kwargs={'partner_id': reel.author.id})
        return JsonResponse({
            'status': 'SENT', 
            'message': 'Handshake Established.',
            'redirect_url': chat_url,
            'is_whatsapp': False
        })
    
    return JsonResponse({'status': 'ERROR', 'message': 'Handshake Failed: Empty Content.'}, status=400)

@login_required
def ai_negotiate_price(request, reel_id):
    """
    Pillar 3: The "Haggle" Protocol.
    """
    if request.method == "POST":
        reel = get_object_or_404(BusinessReel, id=reel_id, is_active=True)
        
        if not reel.price:
            return JsonResponse({
                'status': 'INFO', 
                'message': 'This is a professional showcase. Use "Hire" to discuss customized rates.'
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
            
            counter_offer = max(floor_price * 1.05, buyer_offer * 1.10) 
            counter_offer = min(counter_offer, public_price)
            
            return JsonResponse({
                'status': 'COUNTER', 
                'message': 'Best possible deal:',
                'price': round(counter_offer, 2)
            })
            
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({'status': 'ERROR', 'message': 'Data Handshake Error.'}, status=400)
            
    return JsonResponse({'status': 'ERROR', 'message': 'Protocol Violation.'}, status=405)