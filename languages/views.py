from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from .forms import PhraseContributionForm
from .models import PhraseContribution, LANGUAGES, INTENTS
import json

def contribute(request):
    """
    Handles the contribution form, processing both GET and POST requests.
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
    # Temporarily remove the filter for is_validated to check if any contributions appear.
    contributions = PhraseContribution.objects.all()
    
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
    # Get contributions that are validated
    contributions = PhraseContribution.objects.filter(is_validated=True).values('text', 'translation', 'language', 'intent')
    
    # Serialize the queryset to a JSON list
    data = list(contributions)
    
    # Create the JSON response
    response = JsonResponse(data, safe=False)
    
    # Set the filename for download
    response['Content-Disposition'] = 'attachment; filename="contributions.json"'
    
    return response

def sponsor(request):
    """
    Renders the sponsorship page.
    """
    return render(request, 'sponsor.html')
