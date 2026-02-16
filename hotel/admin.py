from django.contrib import admin
from .models import Accommodation

@admin.register(Accommodation)
class AccommodationAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'country', 'source', 'price_per_night')
    list_filter = ('country', 'source', 'stars')
    search_fields = ('name', 'city', 'country')