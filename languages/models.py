from django.db import models
from django.db.models import Sum # Import Sum for the aggregation function
from django.utils.translation import gettext_lazy as _

# A comprehensive list of Ugandan languages based on the prompt's request.
# This list is representative and can be expanded.
LANGUAGES = (
    ('luganda', 'Luganda'),
    ('acholi', 'Acholi'),
    ('lugbara', 'Lugbara'),
    ('ateso', 'Ateso'),
    ('runyankole', 'Runyankole'),
    ('lusoga', 'Lusoga'),
    ('lumasaba', 'Lumasaba'),
    ('langi', 'Langi'),
    ('kakwa', 'Kakwa'),
    ('aluru', 'Aluru'),
    ('kumam', 'Kumam'),
    ('runyoro', 'Runyoro'),
    ('rukiga', 'Rukiga'),
    ('samia', 'Samia'),
    ('kinyarwanda', 'Kinyarwanda'),
    ('kupsapiiny', 'Kupsapiiny'),
    ('nyangore', 'Nyangore'),
    ('pokot', 'Pokot'),
    ('ik', 'Ik'),
    ('madu', 'Madu'),
    ('madi', 'Madi'),
    ('ma\'di', 'Ma\'di'),
    ('ng`akaramojong', 'Ng`akaramojong'),
    ('sebei', 'Sebei'),
    ('sabiny', 'Sabiny'),
    ('suam', 'Suam'),
    ('chope', 'Chope'),
)

# A comprehensive list of intents or categories for the phrases.
# This helps in classifying the contributions.
INTENTS = (
    ('greetings', 'Greetings & Courtesies'),
    ('travel', 'Travel & Directions'),
    ('food', 'Food & Dining'),
    ('culture', 'Culture & Traditions'),
    ('emergency', 'Emergency Phrases'),
    ('business', 'Business & Commerce'),
    ('medical', 'Medical & Health'),
    ('education', 'Education'),
    ('family', 'Family & Relationships'),
    ('technology', 'Technology & Modern Life'),
    ('expressions', 'Common Expressions & Idioms'),
    ('questions', 'Questions'),
    ('statements', 'Statements'),
)

# New Contributor model to track user-specific data like badges.
class Contributor(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text=_("The name of the contributor."))
    location = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("The location of the contributor.")
    )
    badge = models.CharField(
        max_length=50,
        default="New Contributor",
        help_text=_("The badge earned by the contributor.")
    )

    def __str__(self):
        return self.name
    
    # Custom method to update the contributor's badge based on total likes.
    def update_badge(self):
        # Sum the likes from all contributions associated with this contributor.
        total_likes = self.phrasecontribution_set.aggregate(Sum('likes'))['likes__sum'] or 0
        
        if total_likes >= 100:
            self.badge = "National Language Hero"
        elif total_likes >= 50:
            self.badge = "Regional Linguist"
        elif total_likes >= 10:
            self.badge = "Village Voice"
        else:
            self.badge = "New Contributor"
        self.save()


class PhraseContribution(models.Model):
    """
    Model to store user contributions of words, phrases, and sentences.
    """
    text = models.CharField(max_length=500, help_text=_("The word, phrase, or sentence in a Ugandan language."))
    translation = models.CharField(
        max_length=500, 
        blank=True, 
        null=True, 
        help_text=_("Optional English translation.")
    )
    language = models.CharField(
        max_length=50, 
        choices=LANGUAGES, 
        help_text=_("The Ugandan language of the text.")
    )
    intent = models.CharField(
        max_length=50, 
        choices=INTENTS, 
        help_text=_("The intent or category of the text.")
    )
    # The contributor field is a foreign key to the Contributor model.
    contributor = models.ForeignKey(
        Contributor, 
        on_delete=models.SET_NULL, # If a contributor is deleted, their contributions will remain.
        null=True, 
        blank=True,
        help_text=_("The contributor associated with this phrase.")
    )
    
    # Add contributor name and location fields to the PhraseContribution model.
    # This keeps the data directly accessible without needing a separate lookup.
    contributor_name = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("The name of the contributor.")
    )
    contributor_location = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("The location of the contributor.")
    )

    timestamp = models.DateTimeField(auto_now_add=True)
    is_validated = models.BooleanField(
        default=False, 
        help_text=_("Marks if the contribution has been reviewed and validated.")
    )
    # New field to track the number of likes.
    likes = models.IntegerField(default=0)

    class Meta:
        verbose_name = _("Phrase Contribution")
        verbose_name_plural = _("Phrase Contributions")
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.text} ({self.language})"
