# -*- coding: utf-8 -*-
from django.conf import settings
from django.db import models


class PublicationHistory(models.Model):
    STATUS_QUEUED = 'queued'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_ROLLED_BACK = 'rolled_back'

    platform_listing = models.ForeignKey(
        'catalog.PlatformListing',
        on_delete=models.CASCADE,
        related_name='publications',
    )
    version = models.ForeignKey(
        'creative.CreativeVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='publications',
    )
    snapshot_before_json = models.JSONField(default=dict, blank=True)
    snapshot_after_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, default=STATUS_QUEUED, db_index=True)
    error = models.TextField(blank=True)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '发布历史'
        verbose_name_plural = '发布历史'
        ordering = ['-created_at']


class ManualPerformanceLog(models.Model):
    """MVP：手工录入广告/转化指标，二期再接 API。"""

    platform_listing = models.ForeignKey(
        'catalog.PlatformListing',
        on_delete=models.CASCADE,
        related_name='performance_logs',
    )
    version = models.ForeignKey(
        'creative.CreativeVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    date_from = models.DateField()
    date_to = models.DateField()
    impressions = models.PositiveIntegerField(null=True, blank=True)
    clicks = models.PositiveIntegerField(null=True, blank=True)
    ad_spend = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    orders = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '手工效果记录'
        verbose_name_plural = '手工效果记录'
        ordering = ['-date_to']
