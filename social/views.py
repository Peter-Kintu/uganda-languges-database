import os
import json
import random
import uuid
import urllib.parse
import logging
import cloudinary
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
from .models import (
    BusinessReel, SocialProfile, SecureMessage, 
    YouTubePartnership, YouTubeChannel, YouTubeVideo
)
from .forms import (
    BusinessReelUploadForm, SecureMessageForm,
    YouTubePartnershipForm, YouTubeChannelForm
)
# External User Model from users app
from users.models import CustomUser

logger = logging.getLogger(__name__)

# --- SECURITY: Initialize Cloudinary with secure=True for HTTPS delivery ---
if os.environ.get('CLOUDINARY_CLOUD_NAME'):
    cloudinary.config(
        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
        secure=True  # Force all Cloudinary URLs to use HTTPS
    )


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

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

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
    Pillar 2 & 3: Africa-First Upload Flow with Hybrid Storage (Three-Tier System).
    UPDATED: Saves compressed videos to local server disk (Tier 1) instead of Cloudinary.
    Background task will promote viral videos to Cloudinary CDN (Tier 3) automatically.
    """
    if request.method == 'POST':
        form = BusinessReelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            reel = form.save(commit=False)
            reel.author = request.user
            
            # --- THREE-TIER STORAGE LOGIC ---
            # All new uploads go to local server disk (Choice B)
            if 'video' in request.FILES:
                reel.local_video = request.FILES['video']
                reel.storage_tier = 'LOCAL'  # Initial tier: Local server storage
            
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
            
            messages.success(request, "Deployment Successful: Your reel is live on local streaming.")
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

@login_required
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

@login_required
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
@csrf_exempt
@require_POST
def track_view(request, reel_id):
    """
    Track video views for virality metrics.
    When views exceed threshold (default: 50), background task promotes to Cloudinary.
    """
    reel = get_object_or_404(BusinessReel, id=reel_id)
    reel.views_count = F('views_count') + 1
    reel.save(update_fields=['views_count'])
    reel.refresh_from_db()
    
    return JsonResponse({
        'status': 'SUCCESS',
        'total_views': reel.views_count,
        'storage_tier': reel.storage_tier
    })

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
    
    # Get last message for each partner
    conversations = []
    for partner in chat_partners:
        last_message = SecureMessage.objects.filter(
            (Q(sender=request.user) & Q(recipient=partner)) |
            (Q(sender=partner) & Q(recipient=request.user))
        ).order_by('-created_at').first()
        
        if last_message:
            conversations.append({
                'partner': partner,
                'last_message': last_message,
                'unread_count': SecureMessage.objects.filter(
                    sender=partner, recipient=request.user, is_read=False
                ).count()
            })
    
    # Sort by last message time
    conversations.sort(key=lambda x: x['last_message'].created_at, reverse=True)
    
    return render(request, 'social/inbox.html', {'conversations': conversations})

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


# --- PILLAR 5: YOUTUBE PARTNERSHIP MANAGEMENT ---

@login_required
def apply_youtube_partnership(request):
    """
    Partnership Application: Users submit their intent to sync YouTube content.
    """
    partnership, created = YouTubePartnership.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = YouTubePartnershipForm(request.POST, instance=partnership)
        if form.is_valid():
            form.save()
            messages.success(
                request, 
                "✅ Application submitted! Our team will review it within 24 hours."
            )
            return redirect('social:youtube_partnership_dashboard')
    else:
        form = YouTubePartnershipForm(instance=partnership)
    
    return render(request, 'social/youtube_partnership_apply.html', {
        'form': form,
        'partnership': partnership
    })


@login_required
def youtube_partnership_dashboard(request):
    """
    Dashboard: Users can manage their approved channels and sync status.
    """
    partnership = get_object_or_404(YouTubePartnership, user=request.user)
    
    if partnership.status != 'approved':
        messages.info(
            request,
            f"Your partnership status: {partnership.get_status_display()}. "
            "You'll be able to add channels once approved."
        )
    
    channels = partnership.channels.prefetch_related('videos')
    total_videos = sum(channel.videos.count() for channel in channels)
    context = {
        'partnership': partnership,
        'channels': channels,
        'can_add_channels': partnership.is_active and partnership.status == 'approved',
        'total_videos': total_videos,
    }
    
    return render(request, 'social/youtube_partnership_dashboard.html', context)


@login_required
def add_youtube_channel(request):
    """
    Add a new YouTube channel to sync from.
    Only available for approved partners.
    """
    partnership = get_object_or_404(YouTubePartnership, user=request.user)
    
    if not partnership.is_active or partnership.status != 'approved':
        messages.error(request, "You don't have permission to add channels.")
        return redirect('social:youtube_partnership_dashboard')
    
    if request.method == 'POST':
        form = YouTubeChannelForm(request.POST)
        if form.is_valid():
            try:
                from .youtube_service import YouTubeService
                
                youtube_service = YouTubeService()
                channel_id = form.cleaned_data['channel_id']
                
                # Validate channel exists and fetch info
                channel_info = youtube_service.get_channel_info(channel_id)
                if not channel_info:
                    messages.error(request, "Channel not found. Please check the Channel ID.")
                    return render(request, 'social/add_youtube_channel.html', {'form': form})
                
                # Create or update channel
                youtube_channel, created = YouTubeChannel.objects.get_or_create(
                    partnership=partnership,
                    channel_id=channel_id,
                    defaults={
                        'channel_name': channel_info['channel_name'],
                        'channel_url': channel_info['channel_url'],
                        'channel_thumbnail': channel_info['channel_thumbnail'],
                        'sync_frequency_hours': form.cleaned_data['sync_frequency_hours'],
                    }
                )
                
                if created:
                    messages.success(
                        request,
                        f"✅ Channel '{channel_info['channel_name']}' added successfully! "
                        "We'll start syncing videos shortly."
                    )
                    
                    # Trigger initial sync
                    from .youtube_service import YouTubeSyncService
                    sync_service = YouTubeSyncService()
                    result = sync_service.sync_channel_videos(youtube_channel)
                    
                    if result['synced'] > 0:
                        messages.info(
                            request,
                            f"🎬 Synced {result['synced']} videos from this channel!"
                        )
                else:
                    messages.warning(request, "This channel is already linked to your account.")
                
                return redirect('social:youtube_partnership_dashboard')
            
            except Exception as e:
                logger.error(f"Error adding YouTube channel: {str(e)}")
                messages.error(
                    request,
                    "⚠️ Error connecting to YouTube. Please check your Channel ID and try again."
                )
    else:
        form = YouTubeChannelForm()
    
    return render(request, 'social/add_youtube_channel.html', {'form': form})


@login_required
def remove_youtube_channel(request, channel_id):
    """
    Remove a YouTube channel from syncing.
    """
    partnership = get_object_or_404(YouTubePartnership, user=request.user)
    youtube_channel = get_object_or_404(
        YouTubeChannel,
        id=channel_id,
        partnership=partnership
    )
    
    if request.method == 'POST':
        channel_name = youtube_channel.channel_name
        youtube_channel.delete()
        messages.success(request, f"Removed channel: {channel_name}")
        return redirect('social:youtube_partnership_dashboard')
    
    return render(request, 'social/confirm_remove_youtube_channel.html', {
        'channel': youtube_channel
    })


@login_required
@require_POST
def sync_youtube_channel_now(request, channel_id):
    """
    Manually trigger a sync for a specific channel (admin/partner only).
    """
    partnership = get_object_or_404(YouTubePartnership, user=request.user)
    youtube_channel = get_object_or_404(
        YouTubeChannel,
        id=channel_id,
        partnership=partnership
    )
    
    try:
        from .youtube_service import YouTubeSyncService
        sync_service = YouTubeSyncService()
        result = sync_service.sync_channel_videos(youtube_channel)
        
        message = f"✅ Synced {result['synced']} videos"
        if result['skipped'] > 0:
            message += f" ({result['skipped']} already existed)"
        
        messages.success(request, message)
    except Exception as e:
        logger.error(f"Error syncing channel: {str(e)}")
        messages.error(request, "Error syncing channel. Please try again later.")
    
    return redirect('social:youtube_partnership_dashboard')
