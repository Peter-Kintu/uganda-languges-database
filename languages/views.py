from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.db.models import F
from django.urls import reverse
from .forms import PhraseContributionForm
from .models import PhraseContribution, LANGUAGES, INTENTS
import json

def contribute(request):
    """
    Handles the contribution form, processing both GET and POST requests.
    The form's save() method automatically handles saving the new
    contributor_name and contributor_location fields.
    """
    if request.method == 'POST':
        form = PhraseContributionForm(request.POST)
        if form.is_valid():
            # Save the new contribution to the database
            form.save()
            # Redirect to the same page with a success message
            return redirect('contribute')
    else:
        form = PhraseContributionForm()
    
    return render(request, 'contribute.html', {'form': form})

def browse_contributions(request):
    """
    Displays all validated contributions, with search and filtering capabilities.
    """
    # Filter for only validated contributions.
    contributions = PhraseContribution.objects.filter(is_validated=True)
    
    # Get query parameters for filtering and searching
    language = request.GET.get('language')
    intent = request.GET.get('intent')
    search_query = request.GET.get('search_query')

    # Apply filters
    if language:
        contributions = contributions.filter(language=language)
    if intent:
        contributions = contributions.filter(intent=intent)
    
    # Apply search
    if search_query:
        contributions = contributions.filter(text__icontains=search_query) | \
                        contributions.filter(translation__icontains=search_query)

    context = {
        'contributions': contributions,
        'languages': LANGUAGES,  
        'intents': INTENTS,
        'selected_language': language,
        'selected_intent': intent,
        'search_query': search_query,
    }
    
    return render(request, 'contributions_list.html', context)

def export_contributions_json(request):
    """
    Exports all validated contributions as a JSON file.
    This view is not intended to be accessed directly by the user, but rather
    called as an admin action.
    """
    # Check if the user is authenticated and is a staff member.
    # This is a security measure to prevent unauthorized access.
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponse('Unauthorized', status=401)
        
    # Get contributions that are validated, excluding contributor fields as requested
    contributions = PhraseContribution.objects.filter(is_validated=True).values(
        'text', 
        'translation', 
        'language', 
        'intent'
    )
    
    # Serialize the queryset to a JSON list
    data = list(contributions)
    
    # Create the JSON response
    response = JsonResponse(data, safe=False)
    
    # Set the filename for download
    response['Content-Disposition'] = 'attachment; filename="contributions.json"'
    
    return response

@require_POST
def like_contribution(request, pk):
    """
    Handles incrementing the like count for a specific contribution.
    This view only accepts POST requests.
    """
    # Get the contribution object or return a 404 error
    contribution = get_object_or_404(PhraseContribution, pk=pk)
    # Atomically increment the 'likes' field to avoid race conditions
    contribution.likes = F('likes') + 1
    # Save the change to the database. The update_fields argument is a performance optimization.
    contribution.save(update_fields=['likes'])
    # Redirect back to the browse page, preserving filters and search query
    return redirect(reverse('browse_contributions') + '?' + request.META['QUERY_STRING'])

def sponsor(request):
    """
    Renders the sponsorship page.
    """
    return render(request, 'sponsor.html')

