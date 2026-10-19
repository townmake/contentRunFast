# -*- coding: utf-8 -*-
"""选品连接配置：Admin 库内配置优先，否则回退 .env / Django settings。"""
from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class XuanpinResolvedSettings:
    http_base_url: str
    mcp_base_url: str
    api_key: str
    use_fixtures: bool
    default_ml_site: str
    source: str  # admin | env | mixed


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def resolve_xuanpin_settings() -> XuanpinResolvedSettings:
    env_http = (getattr(settings, 'XUANPIN_HTTP_BASE_URL', '') or '').rstrip('/')
    env_mcp = (getattr(settings, 'XUANPIN_MCP_BASE_URL', '') or '').strip()
    if env_mcp and not env_mcp.endswith('/'):
        env_mcp = env_mcp.rstrip('/') + '/'
    env_key = getattr(settings, 'XUANPIN_MCP_API_KEY', '') or ''
    env_fixtures = _truthy(getattr(settings, 'XUANPIN_USE_FIXTURES', '0'))
    env_site = (getattr(settings, 'MELI_SITE_ID', '') or 'MLB').upper()

    row = None
    try:
        from apps.catalog.models import XuanpinConnectionSettings

        row = XuanpinConnectionSettings.objects.filter(is_active=True).order_by('id').first()
    except Exception:
        # migrate 前 / 表不存在时走 env
        row = None

    if row is None:
        return XuanpinResolvedSettings(
            http_base_url=env_http,
            mcp_base_url=env_mcp,
            api_key=env_key,
            use_fixtures=env_fixtures,
            default_ml_site=env_site,
            source='env',
        )

    http = (row.http_base_url or '').strip().rstrip('/') or env_http
    mcp = (row.mcp_base_url or '').strip() or env_mcp
    if mcp and not mcp.endswith('/'):
        mcp = mcp.rstrip('/') + '/'
    key = (row.api_key or '').strip() or env_key
    site = (row.default_ml_site or '').strip().upper() or env_site
    # Admin 勾选优先；未勾选 fixtures 时仍可读 env（方便本地切换）
    use_fixtures = bool(row.use_fixtures) or env_fixtures

    source = 'admin'
    if (not (row.http_base_url or '').strip() and env_http) or (
        not (row.api_key or '').strip() and env_key
    ):
        source = 'mixed'

    return XuanpinResolvedSettings(
        http_base_url=http,
        mcp_base_url=mcp,
        api_key=key,
        use_fixtures=use_fixtures,
        default_ml_site=site,
        source=source,
    )


def mask_api_key(key: str) -> str:
    k = (key or '').strip()
    if not k:
        return '（未配置）'
    if len(k) <= 8:
        return k[:2] + '***'
    return f'{k[:6]}…{k[-4:]}'
