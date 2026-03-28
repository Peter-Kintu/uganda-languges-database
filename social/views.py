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
    Supports Business (priced) and Professional (showcase) modes.
    """
    if request.method == 'POST':
        form = BusinessReelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            reel = form.save(commit=False)
            reel.author = request.user
            # Generate unique share token if not handled by model save()
            if not hasattr(reel, 'share_token') or not reel.share_token:
                reel.share_token = uuid.uuid4().hex[:12]
            reel.save()
            messages.success(request, "Deployment Successful: Your reel is live on Africana AI.")
            return redirect('social:social_feed')
    else:
        form = BusinessReelUploadForm()

    return render(request, 'social/upload.html', {'form': form})

# --- INTERACTION PROTOCOLS ---

@login_required
@require_POST
def toggle_like_reel(request, reel_id):
    """
    Social Proof: Toggles a like on a reel via AJAX.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    if request.user in reel.likes.all():
        reel.likes.remove(request.user)
        liked = False
    else:
        reel.likes.add(request.user)
        liked = True
    
    return JsonResponse({
        'status': 'success', # Lowercase matches the JS in feed.html
        'liked': liked,
        'total_likes': reel.total_likes() if callable(reel.total_likes) else reel.total_likes
    })

@csrf_exempt # Or ensure X-CSRFToken is passed in JS headers
@require_POST
def track_share(request, reel_id):
    """
    Branding: Increments the share count for metrics.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    BusinessReel.objects.filter(id=reel_id).update(share_count=F('share_count') + 1)
    return JsonResponse({'status': 'SUCCESS'})

@csrf_exempt
@require_POST
def track_download(request, reel_id):
    """
    Performance: Increments download count for professional content.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    BusinessReel.objects.filter(id=reel_id).update(download_count=F('download_count') + 1)
    return JsonResponse({'status': 'SUCCESS'})

# --- AGENTIC & MESSAGING PROTOCOLS ---

@login_required
@require_POST
def initiate_hire_protocol(request, reel_id):
    """
    Sovereign Messaging: The 'Hire' Protocol.
    Handles the "Secure Handshake" between buyer and professional.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    content = request.POST.get('content')
    
    if content:
        msg = SecureMessage.objects.create(
            sender=request.user,
            recipient=reel.author,
            related_reel=reel,
            content=content
        )
        return JsonResponse({'status': 'SENT', 'message': 'Secure Handshake Established.'})
    
    return JsonResponse({'status': 'ERROR', 'message': 'Handshake Failed: Empty Message.'}, status=400)

@login_required
def ai_negotiate_price(request, reel_id):
    """
    Pillar 3: The "Haggle" Protocol.
    Autonomous agent handling price discovery within seller-defined boundaries.
    """
    if request.method == "POST":
        reel = get_object_or_404(BusinessReel, id=reel_id, is_active=True)
        
        if not reel.price:
            return JsonResponse({
                'status': 'INFO', 
                'message': 'This is a professional showcase. Use "Hire" to discuss customized rates.'
            })
        
        try:
            # Handle both JSON and Form data for flexibility
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
                
            buyer_offer = float(data.get('offer', 0))
            # floor_price is the seller's absolute minimum
            floor_price = float(reel.negotiation_floor if hasattr(reel, 'negotiation_floor') else reel.price * 0.8)
            public_price = float(reel.price)
            
            # 1. Instant Acceptance (At or above asking price)
            if buyer_offer >= public_price:
                return JsonResponse({
                    'status': 'SUCCESS', 
                    'message': 'Offer accepted immediately. Proceed to secure checkout.',
                    'price': buyer_offer
                })

            # 2. Agentic Negotiation (Within acceptable range)
            if buyer_offer >= floor_price:
                # If offer is within 5% of asking, accept it to close the deal
                if (public_price - buyer_offer) / public_price <= 0.05:
                     return JsonResponse({
                        'status': 'SUCCESS', 
                        'message': 'The Agent has authorized this deal! Excellent value.',
                        'price': buyer_offer
                    })
                
                # Propose a midpoint if the offer is fair but low
                suggested_midpoint = (public_price + buyer_offer) / 2
                return JsonResponse({
                    'status': 'COUNTER',
                    'message': 'You are close to a deal. The Agent proposes this middle ground:',
                    'price': round(suggested_midpoint, 2)
                })
            
            # 3. Floor Defense (Below minimum acceptable price)
            # The agent counters with the floor price plus a small margin
            counter_offer = max(floor_price * 1.05, buyer_offer * 1.10) 
            counter_offer = min(counter_offer, public_price)
            
            return JsonResponse({
                'status': 'COUNTER', 
                'message': 'That offer is below the authorized floor. The Agent suggests this as the best possible deal:',
                'price': round(counter_offer, 2)
            })
            
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({'status': 'ERROR', 'message': 'Data Handshake Error.'}, status=400)
            
    return JsonResponse({'status': 'ERROR', 'message': 'Protocol Violation.'}, status=405)