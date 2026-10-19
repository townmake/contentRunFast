from django.contrib import admin

from .models import AIGenerationTask, CreativeAsset, CreativeVersion


@admin.register(CreativeAsset)
class CreativeAssetAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'asset_type', 'source', 'created_at')
    list_filter = ('asset_type', 'source')


@admin.register(CreativeVersion)
class CreativeVersionAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'version_code', 'review_status', 'role', 'created_at')
    list_filter = ('review_status', 'role')
    search_fields = ('version_code',)


@admin.register(AIGenerationTask)
class AIGenerationTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'status', 'created_at')
    list_filter = ('status',)
