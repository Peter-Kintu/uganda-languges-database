from django.db import models
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
    ('nyakwai', 'Nyakwai'),
    ('soga', 'Soga'),
    ('ndyaba', 'Ndyaba'),
    ('ndyaba', 'Ndyaba'),
    ('ngboko', 'Ngboko'),
    ('kamba', 'Kamba'),
    ('amadi', 'Amadi'),
    ('sese', 'Sese'),
    ('talinga', 'Talinga'),
    ('nubi', 'Nubi'),
    ('kuku', 'Kuku'),
    ('kuliak', 'Kuliak'),
    ('ng`itome', 'Ng`itome'),
    ('ng`alimo', 'Ng`alimo'),
    ('elgon', 'Elgon'),
)

# Common intents for linguistic contributions. This can also be expanded.
INTENTS = (
    ('greeting', 'Greeting'),
    ('health', 'Health'),
    ('food', 'Food'),
    ('education', 'Education'),
    ('civic_tech', 'Civic Tech'),
    ('nature', 'Nature'),
    ('directions', 'Directions'),
    ('other', 'Other'),
)

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
    contributor_name = models.CharField(
        max_length=100, 
        blank=True, 
        help_text=_("Optional name of the contributor.")
    )
    contributor_location = models.CharField(
        max_length=100, 
        blank=True, 
        help_text=_("Optional location of the contributor.")
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    is_validated = models.BooleanField(
        default=False, 
        help_text=_("Marks if the contribution has been reviewed and validated.")
    )

    class Meta:
        verbose_name = _("Phrase Contribution")
        verbose_name_plural = _("Phrase Contributions")
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.language} | {self.intent}: {self.text[:50]}"
