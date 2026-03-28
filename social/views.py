import os
import json
import random
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

# Internal App Models and Forms
from .models import BusinessReel, SocialProfile
from .forms import BusinessReelUploadForm 
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
    queryset = BusinessReel.objects.filter(is_active=True).select_related('author__social_profile')
    ordering = ['-created_at']

class BentoProfileView(DetailView):
    """
    Pillar 4: LinkedIn 2.0 Bento-style profile view.
    Highlights Trust Ledger and Proof of Work.
    """
    model = CustomUser
    template_name = 'social/bento_profile.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['social'] = self.object.social_profile
        context['user_reels'] = BusinessReel.objects.filter(author=self.object, is_active=True)
        # Fetch verified video endorsements for the 'Proof of Work' section
        context['endorsements'] = self.object.received_endorsements.filter(is_verified_transaction=True)[:5]
        return context

@login_required
def upload_reel(request):
    """
    Pillar 2 & 3: Africa-First Upload Flow.
    Sets the stage for Agentic Commerce by defining price floors.
    """
    if request.method == 'POST':
        form = BusinessReelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            reel = form.save(commit=False)
            reel.author = request.user
            reel.save()
            return redirect('social:social_feed')
    else:
        form = BusinessReelUploadForm()

    return render(request, 'social/upload.html', {'form': form})

@login_required
def ai_negotiate_price(request, reel_id):
    """
    Pillar 3: The "Haggle" Protocol (2026 Gold Standard).
    An autonomous agent that manages price discovery to save human time.
    """
    if request.method == "POST":
        reel = get_object_or_404(BusinessReel, id=reel_id, is_active=True)
        
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
                
            buyer_offer = float(data.get('offer', 0))
            floor_price = float(reel.get_negotiation_floor())
            public_price = float(reel.price)
            
            # --- AGENTIC LOGIC: THE HAGGLE ---
            
            # 1. Instant Acceptance
            if buyer_offer >= public_price:
                return JsonResponse({
                    'status': 'SUCCESS', 
                    'message': 'Excellent choice! Your offer is accepted immediately.',
                    'price': buyer_offer
                })

            # 2. Strategic Negotiation (The "Middle Ground")
            if buyer_offer >= floor_price:
                # If the offer is above floor but below public, the AI tries to 
                # meet them halfway to maximize profit for the seller.
                suggested_midpoint = (public_price + buyer_offer) / 2
                
                # If the difference is small (less than 5%), just accept it to close the deal.
                if (public_price - buyer_offer) / public_price < 0.05:
                     return JsonResponse({
                        'status': 'SUCCESS', 
                        'message': 'Deal! The Africana Agent has accepted your offer.',
                        'price': buyer_offer
                    })
                
                return JsonResponse({
                    'status': 'COUNTER',
                    'message': 'You are close! How about we meet in the middle?',
                    'price': round(suggested_midpoint, 2)
                })
            
            # 3. Floor Protection
            # If offer is too low, counter with a price slightly above the floor
            # to leave room for one final concession.
            counter_offer = floor_price * 1.05 
            
            return JsonResponse({
                'status': 'COUNTER', 
                'message': 'That is a bit low for this quality. Here is the best the Agent can do right now.',
                'price': round(counter_offer, 2)
            })
            
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({'status': 'ERROR', 'message': 'Invalid offer data.'}, status=400)
            
    return JsonResponse({'status': 'ERROR', 'message': 'Method not allowed.'}, status=405)