# languages/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.db.models import F, Q, Count
from django.urls import reverse
from datetime import date
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Import your models and static lists from your models.py file
from .forms import PhraseContributionForm
from .models import PhraseContribution, LANGUAGES, INTENTS


def get_top_contributors(month=None, year=None, limit=10):
    """
    A helper function to find and count top contributors.
    It can be filtered by month and year, or used for all-time stats.
    Returns a list of dictionaries with contributor_name and contribution_count.
    """
    query_set = PhraseContribution.objects.all()

    # Apply date filters if provided
    if month and year:
        query_set = query_set.filter(timestamp__month=month, timestamp__year=year)

    # Annotate and order by contribution count
    top_contributors = query_set.values('contributor_name').annotate(
        contribution_count=Count('contributor_name')
    ).order_by('-contribution_count')[:limit]

    return top_contributors


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
            # Redirect to the same page with a success message.
            # We use the namespaced URL 'languages:contribute' to prevent errors.
            return redirect('languages:contribute')
    else:
        form = PhraseContributionForm()
    
    return render(request, 'contribute.html', {'form': form})


def browse_contributions(request):
    """
    Displays all validated contributions, with search and filtering capabilities.
    This view has been updated to use Django's ORM more effectively.
    """
    # Start with a base queryset of all contributions.
    # The filter for `is_validated=True` has been removed to display all contributions.
    contributions = PhraseContribution.objects.all()
    
    # Get query parameters for filtering and searching.
    selected_language = request.GET.get('language')
    selected_intent = request.GET.get('intent')
    search_query = request.GET.get('search_query')

    # Add debugging print statements to confirm query parameters
    print("Language:", selected_language)
    print("Intent:", selected_intent)
    print("Search:", search_query)

    # Build a dynamic query using a Q object.
    # This approach is cleaner and more scalable than chained filters.
    query_filters = Q()

    # Apply language filter if a language is selected.
    if selected_language:
        query_filters &= Q(language=selected_language)

    # Apply intent filter if an intent is selected.
    if selected_intent:
        query_filters &= Q(intent=selected_intent)
    
    # Apply search filter across both 'text' and 'translation' fields.
    if search_query:
        query_filters &= Q(text__icontains=search_query) | Q(translation__icontains=search_query)

    # Filter the contributions using the constructed Q object.
    contributions = contributions.filter(query_filters)

    # Add a debugging print statement to confirm the count
    print("Filtered contributions count:", contributions.count())

    # Order the contributions by the number of likes in descending order.
    # This promotes the most popular contributions.
    contributions = contributions.order_by('-likes', 'timestamp')

    # Add pagination for scalability
    paginator = Paginator(contributions, 20)  # Show 20 contributions per page.
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page_obj = paginator.get_page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results.
        page_obj = paginator.get_page(paginator.num_pages)

    # Prepare the context to pass to the template.
    context = {
        'page_obj': page_obj, # Pass the paginated object instead of the full queryset
        'contributions': page_obj,
        'languages': LANGUAGES, # Use the static list
        'intents': INTENTS, # Use the static list
        'selected_language': selected_language,
        'selected_intent': selected_intent,
        'search_query': search_query,
    }
    
    # Revert the template path to the original, which should exist.
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
    # The 'reverse' function is used to dynamically build the URL with the correct namespace.
    return redirect(reverse('languages:browse_contributions') + '?' + request.META['QUERY_STRING'])


def sponsor(request):
    """
    Renders the sponsorship page and fetches top contributors.
    """
    # Use the new helper function to get all-time top contributors
    top_contributors = get_top_contributors(limit=10)

    context = {
        'top_contributors': top_contributors
    }
    return render(request, 'sponsor.html', context)
    

def best_contributor_view(request):
    """
    Finds and displays the best contributor of the current month.
    """
    today = date.today()
    
    # Use the new helper function to get the top contributor for the current month
    best_contributor_data = get_top_contributors(month=today.month, year=today.year, limit=1).first()
    
    # Prepare the context dictionary to pass to the template
    context = {}
    if best_contributor_data:
        context['contributor_name'] = best_contributor_data['contributor_name']
        context['contribution_count'] = best_contributor_data['contribution_count']
    else:
        context['message'] = "No contributions have been made yet this month. Be the first to add one!"

    # Render the template with the prepared context
    return render(request, 'best_contributor.html', context)
