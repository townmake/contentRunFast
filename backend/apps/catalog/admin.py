# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from django.contrib import admin, messages
from django.forms import PasswordInput
from django.utils import timezone
from django.utils.html import format_html

from .models import PlatformListing, ProductMaster, XuanpinConnectionSettings
from .services.settings_resolve import mask_api_key, resolve_xuanpin_settings

logger = logging.getLogger(__name__)


@admin.register(XuanpinConnectionSettings)
class XuanpinConnectionSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'label', 'is_active', 'http_base_url', 'masked_key',
        'default_ml_site', 'use_fixtures', 'test_badge', 'updated_at',
    )
    list_filter = ('is_active', 'use_fixtures', 'default_ml_site')
    readonly_fields = (
        'created_at', 'updated_at', 'last_tested_at', 'last_test_ok', 'last_test_message',
        'resolved_preview',
    )
    actions = ('action_test_connection', 'action_deactivate_others')
    fieldsets = (
        (None, {
            'fields': ('label', 'is_active', 'use_fixtures', 'default_ml_site'),
        }),
        ('连接', {
            'fields': ('http_base_url', 'mcp_base_url', 'api_key'),
            'description': (
                '填写后优先于 .env。Key 须在选品系统绑定默认用户，'
                '且该用户对目标 ProductListing 有 can_view。'
            ),
        }),
        ('探测与说明', {
            'fields': (
                'notes',
                'resolved_preview',
                'last_tested_at', 'last_test_ok', 'last_test_message',
                'created_at', 'updated_at',
            ),
        }),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'api_key':
            kwargs['widget'] = PasswordInput(render_value=True, attrs={'style': 'width: 28em'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description='API Key')
    def masked_key(self, obj: XuanpinConnectionSettings):
        return mask_api_key(obj.api_key)

    @admin.display(description='探测')
    def test_badge(self, obj: XuanpinConnectionSettings):
        if obj.last_test_ok is True:
            return format_html('<span style="color:#0a0">成功</span>')
        if obj.last_test_ok is False:
            return format_html('<span style="color:#a00">失败</span>')
        return '—'

    @admin.display(description='当前实际生效配置')
    def resolved_preview(self, obj: XuanpinConnectionSettings):
        cfg = resolve_xuanpin_settings()
        return (
            f'source={cfg.source}\n'
            f'http={cfg.http_base_url or "（空）"}\n'
            f'mcp={cfg.mcp_base_url or "（空）"}\n'
            f'key={mask_api_key(cfg.api_key)}\n'
            f'fixtures={cfg.use_fixtures}\n'
            f'ml_site={cfg.default_ml_site}'
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.is_active:
            (
                XuanpinConnectionSettings.objects
                .exclude(pk=obj.pk)
                .filter(is_active=True)
                .update(is_active=False)
            )

    @admin.action(description='测试选品连接（GET open/listings/?limit=1）')
    def action_test_connection(self, request, queryset):
        from .services.xuanpin_http_client import XuanpinListingClient

        for obj in queryset:
            # 临时启用本条来解析（探测前写库状态）
            was_active = obj.is_active
            if not was_active:
                obj.is_active = True
                obj.save(update_fields=['is_active'])
                XuanpinConnectionSettings.objects.exclude(pk=obj.pk).filter(
                    is_active=True,
                ).update(is_active=False)

            cfg = resolve_xuanpin_settings()
            client = XuanpinListingClient(
                base_url=cfg.http_base_url,
                api_key=cfg.api_key,
                use_fixtures=cfg.use_fixtures,
            )
            try:
                data = client.list_product_listings(limit=1, ml_site=cfg.default_ml_site)
                count = data.get('count', len(data.get('items') or []))
                obj.last_tested_at = timezone.now()
                obj.last_test_ok = True
                obj.last_test_message = f'OK count={count} fixtures={cfg.use_fixtures}'
                obj.save(update_fields=[
                    'last_tested_at', 'last_test_ok', 'last_test_message', 'updated_at',
                ])
                self.message_user(
                    request,
                    f'「{obj.label}」连接成功：{obj.last_test_message}',
                    level=messages.SUCCESS,
                )
            except Exception as exc:
                logger.info('xuanpin connection test failed: %s', exc)
                obj.last_tested_at = timezone.now()
                obj.last_test_ok = False
                obj.last_test_message = str(exc)[:500]
                obj.save(update_fields=[
                    'last_tested_at', 'last_test_ok', 'last_test_message', 'updated_at',
                ])
                self.message_user(
                    request,
                    f'「{obj.label}」连接失败：{exc}',
                    level=messages.ERROR,
                )

            if not was_active:
                obj.is_active = False
                obj.save(update_fields=['is_active'])

    @admin.action(description='停用其他配置（只留勾选的启用）')
    def action_deactivate_others(self, request, queryset):
        ids = list(queryset.values_list('id', flat=True))
        if not ids:
            return
        XuanpinConnectionSettings.objects.filter(id__in=ids).update(is_active=True)
        n = (
            XuanpinConnectionSettings.objects
            .exclude(id__in=ids)
            .filter(is_active=True)
            .update(is_active=False)
        )
        # 若勾选多条，只保留 id 最小的一条启用
        keep = min(ids)
        XuanpinConnectionSettings.objects.filter(id__in=ids).exclude(id=keep).update(is_active=False)
        self.message_user(request, f'已启用 #{keep}，另停用 {n} 条其他启用项')


@admin.register(ProductMaster)
class ProductMasterAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'internal_sku', 'xuanpin_listing_id', 'updated_at')
    search_fields = ('name', 'internal_sku')


@admin.register(PlatformListing)
class PlatformListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'platform', 'ml_site', 'item_id', 'sync_status')
    list_filter = ('platform', 'ml_site')
