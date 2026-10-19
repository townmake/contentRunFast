# -*- coding: utf-8 -*-
from django.db import models


class XuanpinConnectionSettings(models.Model):
    """选品系统连接配置（Admin 可改；优先于 .env）。建议只保留一条启用记录。"""

    label = models.CharField('名称', max_length=100, default='默认选品连接')
    http_base_url = models.CharField(
        '选品 HTTP Base',
        max_length=500,
        blank=True,
        help_text='例：http://127.0.0.1:8000 或 https://pro.linzz.cn（不要末尾斜杠）',
    )
    mcp_base_url = models.CharField(
        '选品 MCP Base',
        max_length=500,
        blank=True,
        help_text='例：http://127.0.0.1:8000/mcp/ （需以 /mcp/ 结尾）',
    )
    api_key = models.CharField(
        'MCP API Key',
        max_length=500,
        blank=True,
        help_text='选品 Admin 签发的 mcp_… 密钥；须绑定默认用户且对该 Listing 有查看权',
    )
    default_ml_site = models.CharField(
        '默认站点', max_length=8, default='MLB', blank=True,
        help_text='MLB=巴西 / MLM=墨西哥',
    )
    use_fixtures = models.BooleanField(
        '使用本地假数据',
        default=False,
        help_text='勾选后不访问真实选品（仅开发自测）',
    )
    is_active = models.BooleanField('启用', default=True)
    notes = models.TextField('备注', blank=True)
    last_tested_at = models.DateTimeField('最近探测时间', null=True, blank=True)
    last_test_ok = models.BooleanField('最近探测成功', null=True, blank=True)
    last_test_message = models.CharField('最近探测结果', max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '选品连接配置'
        verbose_name_plural = '选品连接配置'
        ordering = ['-is_active', 'id']

    def __str__(self):
        state = '启用' if self.is_active else '停用'
        return f'{self.label}（{state}）'


class ProductMaster(models.Model):
    """内部商品主档：大量调研字段引用选品，不整表复制 DevProject。"""

    name = models.CharField('名称', max_length=500)
    internal_sku = models.CharField('内部SKU', max_length=100, blank=True, db_index=True)
    xuanpin_listing_id = models.PositiveIntegerField(
        '选品 ProductListing.id', null=True, blank=True, db_index=True,
    )
    xuanpin_dev_project_id = models.PositiveIntegerField(
        '选品 DevProject.id', null=True, blank=True, db_index=True,
    )
    cover_image_url = models.URLField('封面图', max_length=2000, blank=True)
    xuanpin_context_json = models.JSONField('选品上下文缓存', default=dict, blank=True)
    xuanpin_fetched_at = models.DateTimeField('选品上下文拉取时间', null=True, blank=True)
    status = models.CharField('状态', max_length=32, default='active', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '商品主档'
        verbose_name_plural = '商品主档'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name or f'Product#{self.pk}'


class PlatformListing(models.Model):
    """内部商品 ↔ 平台链接映射。"""

    PLATFORM_ML = 'mercadolibre'
    PLATFORM_SHOPEE = 'shopee'
    PLATFORM_TIKTOK = 'tiktok'
    PLATFORM_CHOICES = [
        (PLATFORM_ML, 'Mercado Libre'),
        (PLATFORM_SHOPEE, 'Shopee'),
        (PLATFORM_TIKTOK, 'TikTok Shop'),
    ]

    product = models.ForeignKey(
        ProductMaster, on_delete=models.CASCADE, related_name='platform_listings',
    )
    platform = models.CharField(max_length=32, choices=PLATFORM_CHOICES, db_index=True)
    ml_site = models.CharField('站点', max_length=8, blank=True, default='MLB')
    item_id = models.CharField('平台商品ID', max_length=64, db_index=True)
    user_product_id = models.CharField('User Product ID', max_length=64, blank=True)
    shop_account = models.ForeignKey(
        'platforms.PlatformAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='listings',
    )
    permalink = models.URLField(max_length=2000, blank=True)
    sync_status = models.CharField(max_length=32, default='unknown')
    current_version = models.ForeignKey(
        'creative.CreativeVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '平台链接映射'
        verbose_name_plural = '平台链接映射'
        unique_together = [('platform', 'ml_site', 'item_id')]
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.platform}:{self.item_id}'
