import os
import json
import random
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.db.models import F

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
    queryset = BusinessReel.objects.filter(is_active=True).select_related('author__social_profile')
    ordering = ['-created_at']

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
        # Fetch verified video endorsements
        context['endorsements'] = self.object.received_endorsements.filter(is_verified_transaction=True)[:5]
        return context

@login_required
def upload_reel(request):
    """
    Pillar 2 & 3: Africa-First Upload Flow.
    Supports Business (priced) and Professional (showcase) modes.
    """
    if request.method == 'POST':
        form = BusinessReelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            reel = form.save(commit=False)
            reel.author = request.user
            reel.save()
            messages.success(request, "Deployment Successful: Your reel is live on Africana AI.")
            return redirect('social:social_feed')
    else:
        form = BusinessReelUploadForm()

    return render(request, 'social/upload.html', {'form': form})

# --- INTERACTION PROTOCOLS (NEW) ---

@login_required
@require_POST
def toggle_like_reel(request, reel_id):
    """
    Social Proof: Toggles a like on a reel.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    if request.user in reel.likes.all():
        reel.likes.remove(request.user)
        liked = False
    else:
        reel.likes.add(request.user)
        liked = True
    
    return JsonResponse({
        'status': 'SUCCESS',
        'liked': liked,
        'total_likes': reel.total_likes
    })

@require_POST
def track_share(request, reel_id):
    """
    Branding: Increments the share count for Africana AI metrics.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    reel.share_count = F('share_count') + 1
    reel.save()
    return JsonResponse({'status': 'SUCCESS'})

@require_POST
def track_download(request, reel_id):
    """
    Performance: Increments download count for high-value professional content.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    reel.download_count = F('download_count') + 1
    reel.save()
    return JsonResponse({'status': 'SUCCESS'})

# --- AGENTIC & MESSAGING PROTOCOLS ---

@login_required
def initiate_hire_protocol(request, reel_id):
    """
    Sovereign Messaging: The 'Hire' Protocol.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    
    if request.method == 'POST':
        form = SecureMessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.recipient = reel.author
            msg.related_reel = reel
            msg.save()
            return JsonResponse({'status': 'SENT', 'message': 'Secure Handshake Established.'})
    
    return JsonResponse({'status': 'ERROR', 'message': 'Handshake Failed.'}, status=400)

@login_required
def ai_negotiate_price(request, reel_id):
    """
    Pillar 3: The "Haggle" Protocol.
    Autonomous agent handling price discovery.
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
            floor_price = float(reel.get_negotiation_floor() or reel.price)
            public_price = float(reel.price)
            
            # 1. Instant Acceptance
            if buyer_offer >= public_price:
                return JsonResponse({
                    'status': 'SUCCESS', 
                    'message': 'Offer accepted immediately. Proceed to payment.',
                    'price': buyer_offer
                })

            # 2. Agentic Negotiation
            if buyer_offer >= floor_price:
                if (public_price - buyer_offer) / public_price < 0.05:
                     return JsonResponse({
                        'status': 'SUCCESS', 
                        'message': 'The Agent has authorized this deal!',
                        'price': buyer_offer
                    })
                
                suggested_midpoint = (public_price + buyer_offer) / 2
                return JsonResponse({
                    'status': 'COUNTER',
                    'message': 'You are close. The Agent proposes this middle ground:',
                    'price': round(suggested_midpoint, 2)
                })
            
            # 3. Floor Defense
            counter_offer = max(floor_price * 1.05, buyer_offer * 1.10) 
            counter_offer = min(counter_offer, public_price)
            
            return JsonResponse({
                'status': 'COUNTER', 
                'message': 'That offer is below the authorized floor. Best possible deal:',
                'price': round(counter_offer, 2)
            })
            
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({'status': 'ERROR', 'message': 'Data Handshake Error.'}, status=400)
            
    return JsonResponse({'status': 'ERROR', 'message': 'Protocol Violation.'}, status=405)