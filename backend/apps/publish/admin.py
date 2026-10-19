from django.contrib import admin

from .models import ManualPerformanceLog, PublicationHistory


@admin.register(PublicationHistory)
class PublicationHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'platform_listing', 'version', 'status', 'operator', 'published_at', 'created_at',
    )
    list_filter = ('status',)
    search_fields = ('platform_listing__item_id', 'error')
    readonly_fields = (
        'snapshot_before_json', 'snapshot_after_json', 'created_at', 'published_at',
    )


@admin.register(ManualPerformanceLog)
class ManualPerformanceLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'platform_listing', 'version', 'date_from', 'date_to', 'orders', 'ad_spend',
    )
