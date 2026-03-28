import os
import json
import random
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages

# Internal App Models and Forms
from .models import BusinessReel, SocialProfile, SecureMessage
from .forms import BusinessReelUploadForm, SecureMessageForm
# External User Model from users app
from users.models import CustomUser

class FeedView(ListView):
    """
    Pillar 2: Main social feed displaying Business Reels.
    Optimized with select_related for high-speed performance on mobile networks.
    """
    model = BusinessReel
    template_name = 'social/feed.html'
    context_object_name = 'reels'
    # Show both Business (priced) and Professional (unpriced) reels
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
        # Ensure profile exists via the signal-backed relation
        context['social'] = getattr(self.object, 'social_profile', None)
        context['user_reels'] = BusinessReel.objects.filter(author=self.object, is_active=True)
        # Fetch verified video endorsements for the 'Proof of Work' section
        context['endorsements'] = self.object.received_endorsements.filter(is_verified_transaction=True)[:5]
        return context

@login_required
def upload_reel(request):
    """
    Pillar 2 & 3: Africa-First Upload Flow.
    Supports dual-mode uploads: Business (with price) and Professional (no price).
    """
    if request.method == 'POST':
        form = BusinessReelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            reel = form.save(commit=False)
            reel.author = request.user
            reel.save()
            messages.success(request, "Reel deployed successfully to the global feed.")
            return redirect('social:social_feed')
    else:
        form = BusinessReelUploadForm()

    return render(request, 'social/upload.html', {'form': form})

@login_required
def initiate_hire_protocol(request, reel_id):
    """
    Sovereign Messaging: The 'Hire' Protocol.
    Opens a secure channel between a buyer and a professional regarding a specific reel.
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
            return JsonResponse({'status': 'SENT', 'message': 'Inquiry sent securely.'})
    
    return JsonResponse({'status': 'ERROR', 'message': 'Invalid request.'}, status=400)

@login_required
def ai_negotiate_price(request, reel_id):
    """
    Pillar 3: The "Haggle" Protocol.
    Autonomous agent handling price discovery. 
    Gracefully exits if the reel is non-commercial (Professional Mode).
    """
    if request.method == "POST":
        reel = get_object_or_404(BusinessReel, id=reel_id, is_active=True)
        
        # SAFETY: Exit if the reel has no price (Professional Mode)
        if not reel.price:
            return JsonResponse({
                'status': 'INFO', 
                'message': 'This is a professional showcase. Use the "Hire" button to discuss rates.'
            }, status=200)
        
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
                
            buyer_offer = float(data.get('offer', 0))
            floor_price = float(reel.get_negotiation_floor() or reel.price)
            public_price = float(reel.price)
            
            # --- AGENTIC LOGIC: THE HAGGLE ---
            
            # 1. Instant Acceptance (At or above public price)
            if buyer_offer >= public_price:
                return JsonResponse({
                    'status': 'SUCCESS', 
                    'message': 'Excellent choice! Your offer is accepted immediately.',
                    'price': buyer_offer
                })

            # 2. Strategic Negotiation (Above floor, below public)
            if buyer_offer >= floor_price:
                # Close Deal Check: If within 5% of public price, just accept
                if (public_price - buyer_offer) / public_price < 0.05:
                     return JsonResponse({
                        'status': 'SUCCESS', 
                        'message': 'Deal! The Agent has accepted your offer.',
                        'price': buyer_offer
                    })
                
                # Meet in the middle logic
                suggested_midpoint = (public_price + buyer_offer) / 2
                return JsonResponse({
                    'status': 'COUNTER',
                    'message': 'You are close! How about we meet in the middle?',
                    'price': round(suggested_midpoint, 2)
                })
            
            # 3. Floor Protection (Offer is below floor)
            # Counter with 5% above the absolute floor
            counter_offer = max(floor_price * 1.05, buyer_offer * 1.10) 
            # Ensure counter never exceeds public price
            counter_offer = min(counter_offer, public_price)
            
            return JsonResponse({
                'status': 'COUNTER', 
                'message': 'That is a bit low. Here is the best the Agent can do right now.',
                'price': round(counter_offer, 2)
            })
            
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({'status': 'ERROR', 'message': 'Invalid offer data.'}, status=400)
            
    return JsonResponse({'status': 'ERROR', 'message': 'Method not allowed.'}, status=405)