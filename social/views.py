import os
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

# Internal App Models and Forms
from .models import BusinessReel, SocialProfile
from .forms import BusinessReelUploadForm  # Added import to fix Pillar 3 buttons
# External User Model from users app
from users.models import CustomUser

class FeedView(ListView):
    """
    Pillar 2: Main social feed displaying Business Reels.
    Optimized with select_related to fetch author profiles in one query.
    """
    model = BusinessReel
    template_name = 'social/feed.html'
    context_object_name = 'reels'
    # Optimization: select_related prevents 'N+1' queries for the user profiles
    queryset = BusinessReel.objects.filter(is_active=True).select_related('author__social_profile')
    ordering = ['-created_at']

class BentoProfileView(DetailView):
    """
    Pillar 4: A modern 'Bento-style' profile view.
    """
    model = CustomUser
    template_name = 'social/bento_profile.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Signals guarantee the profile exists, so we can access it directly
        context['social'] = self.object.social_profile
        context['user_reels'] = BusinessReel.objects.filter(author=self.object, is_active=True)
        return context

@login_required
def upload_reel(request):
    """
    The 'Africa-First' Upload Flow.
    Uses BusinessReelUploadForm to handle video uploads and AI floor price logic.
    """
    if request.method == 'POST':
        # Pass both POST data and FILES (video) to the form for processing
        form = BusinessReelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            reel = form.save(commit=False)
            reel.author = request.user
            # is_low_bandwidth_optimized defaults to True in the model
            reel.save()
            return redirect('social:social_feed')
    else:
        form = BusinessReelUploadForm()

    # Pass the form to the template to fix input binding
    return render(request, 'social/upload.html', {'form': form})

@login_required
def ai_negotiate_price(request, reel_id):
    """
    Pillar 3: The 'Haggle' Protocol.
    Uses model-level logic to decide counter-offers.
    """
    if request.method == "POST":
        reel = get_object_or_404(BusinessReel, id=reel_id, is_active=True)
        
        try:
            # Handle both JSON (for JS fetch) and standard Form POST
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
                
            buyer_offer = float(data.get('offer', 0))
            
            # Logic encapsulated in the model (checks reel floor OR profile margin)
            floor_price = float(reel.get_negotiation_floor())
            
            if buyer_offer >= floor_price:
                return JsonResponse({
                    'status': 'SUCCESS', 
                    'message': 'Offer accepted by Africana AI Agent.',
                    'price': buyer_offer
                })
            
            # Counter-offer logic: suggest the floor price
            return JsonResponse({
                'status': 'COUNTER', 
                'message': 'The offer is below the acceptable threshold.',
                'price': round(floor_price, 2)
            })
            
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({'status': 'ERROR', 'message': 'Invalid offer data.'}, status=400)
            
    return JsonResponse({'status': 'ERROR', 'message': 'Method not allowed.'}, status=405)