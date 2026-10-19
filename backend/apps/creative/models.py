# -*- coding: utf-8 -*-
from django.db import models


class CreativeAsset(models.Model):
    TYPE_IMAGE = 'image'
    TYPE_COPY = 'copy'
    TYPE_VIDEO = 'video'
    TYPE_CHOICES = [
        (TYPE_IMAGE, '图片'),
        (TYPE_COPY, '文案'),
        (TYPE_VIDEO, '视频'),
    ]

    product = models.ForeignKey(
        'catalog.ProductMaster', on_delete=models.CASCADE, related_name='assets',
    )
    asset_type = models.CharField(max_length=16, choices=TYPE_CHOICES, db_index=True)
    uri = models.CharField(max_length=2000, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    source = models.CharField(max_length=32, default='ai')  # ai|upload|xuanpin
    meta_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '素材资产'
        verbose_name_plural = '素材资产'


class CreativeVersion(models.Model):
    ROLE_CANDIDATE = 'candidate'
    ROLE_CURRENT = 'current'
    ROLE_WINNER = 'winner'
    ROLE_ARCHIVED = 'archived'

    REVIEW_DRAFT = 'draft'
    REVIEW_PENDING = 'pending_review'
    REVIEW_APPROVED = 'approved'
    REVIEW_REJECTED = 'rejected'
    REVIEW_PUBLISHED = 'published'

    product = models.ForeignKey(
        'catalog.ProductMaster', on_delete=models.CASCADE, related_name='versions',
    )
    version_code = models.CharField(max_length=64, db_index=True)
    role = models.CharField(max_length=32, default=ROLE_CANDIDATE)
    review_status = models.CharField(max_length=32, default=REVIEW_DRAFT, db_index=True)
    payload = models.JSONField('版本内容（图序/文案）', default=dict, blank=True)
    prompt = models.TextField(blank=True)
    model_name = models.CharField(max_length=128, blank=True)
    assets = models.ManyToManyField(CreativeAsset, blank=True, related_name='versions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '素材版本'
        verbose_name_plural = '素材版本'
        ordering = ['-created_at']


class AIGenerationTask(models.Model):
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'

    product = models.ForeignKey(
        'catalog.ProductMaster', on_delete=models.CASCADE, related_name='ai_tasks',
    )
    params_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, default=STATUS_QUEUED, db_index=True)
    cost_cents = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    result_version_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI生成任务'
        verbose_name_plural = 'AI生成任务'
        ordering = ['-created_at']
