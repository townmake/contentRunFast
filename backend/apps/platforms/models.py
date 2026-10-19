# -*- coding: utf-8 -*-
from django.db import models


class PlatformAccount(models.Model):
    platform = models.CharField(max_length=32, db_index=True)
    ml_site = models.CharField(max_length=8, blank=True, default='MLB')
    label = models.CharField(max_length=200)
    token_ref = models.CharField(
        'Token引用/密文占位', max_length=500, blank=True,
        help_text='勿明文入库生产密钥；可用环境变量名或密钥管理引用',
    )
    scopes_json = models.JSONField(default=list, blank=True)
    capability_json = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"read_product":"supported","write_images":"needs_permission",...}',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '平台账号'
        verbose_name_plural = '平台账号'

    def __str__(self):
        return f'{self.label} ({self.platform}/{self.ml_site})'
