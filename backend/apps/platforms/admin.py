from django.contrib import admin

from .models import PlatformAccount


@admin.register(PlatformAccount)
class PlatformAccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'label', 'platform', 'ml_site', 'is_active', 'updated_at')
    list_filter = ('platform', 'ml_site', 'is_active')
    search_fields = ('label', 'token_ref')
