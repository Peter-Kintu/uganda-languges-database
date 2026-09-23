from django.contrib import admin

from .models import DriverProfile, RideLocation, RidePayment, RideRating, RideRequest, SafetyReport, SupportTicket


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'vehicle_type', 'vehicle_plate', 'status', 'is_available', 'rating', 'completed_trips')
    list_filter = ('status', 'vehicle_type', 'is_available')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone', 'vehicle_plate')
    actions = ('verify_drivers', 'suspend_drivers')

    @admin.action(description='Verify selected drivers')
    def verify_drivers(self, request, queryset):
        queryset.update(status='verified')

    @admin.action(description='Suspend selected drivers')
    def suspend_drivers(self, request, queryset):
        queryset.update(status='suspended', is_available=False)


@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'rider', 'driver', 'status', 'ride_type', 'payment_method', 'estimated_fare_max', 'requested_at')
    list_filter = ('status', 'ride_type', 'payment_method')
    search_fields = ('pickup_landmark', 'dropoff_landmark', 'rider__username', 'driver__user__username')
    readonly_fields = ('requested_at', 'assigned_at', 'completed_at', 'updated_at')


@admin.register(RidePayment)
class RidePaymentAdmin(admin.ModelAdmin):
    list_display = ('ride', 'provider', 'amount', 'status', 'reference', 'created_at')
    list_filter = ('provider', 'status')
    search_fields = ('ride__rider__username', 'provider_transaction_id')


@admin.register(RideRating)
class RideRatingAdmin(admin.ModelAdmin):
    list_display = ('ride', 'driver', 'score', 'created_at')
    list_filter = ('score',)


@admin.register(SafetyReport)
class SafetyReportAdmin(admin.ModelAdmin):
    list_display = ('ride', 'reporter', 'category', 'status', 'created_at')
    list_filter = ('category', 'status')
    search_fields = ('details', 'reporter__username')


@admin.register(RideLocation)
class RideLocationAdmin(admin.ModelAdmin):
    list_display = ('ride', 'driver', 'latitude', 'longitude', 'recorded_at')
    list_filter = ('driver',)
    readonly_fields = ('recorded_at',)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'requester', 'ride', 'priority', 'status', 'created_at')
    list_filter = ('priority', 'status')
    search_fields = ('subject', 'details', 'requester__username')
    actions = ('mark_in_progress', 'mark_resolved')

    @admin.action(description='Mark selected tickets in progress')
    def mark_in_progress(self, request, queryset):
        queryset.update(status='in_progress')

    @admin.action(description='Resolve selected tickets')
    def mark_resolved(self, request, queryset):
        queryset.update(status='resolved')
