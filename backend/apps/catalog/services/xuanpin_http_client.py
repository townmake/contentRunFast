# -*- coding: utf-8 -*-
"""选品 Listing 只读 HTTP 客户端（契约见 docs/API-CONTRACTS.md §2）。"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import requests

from .exceptions import XuanpinAPIError, XuanpinConfigError
from . import fixtures
from .settings_resolve import resolve_xuanpin_settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
OPEN_PREFIX = '/product-development/api/open'


class XuanpinListingClient:
    """调用选品 open Listing 只读路由。"""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        use_fixtures: bool | None = None,
        session: requests.Session | None = None,
    ):
        cfg = resolve_xuanpin_settings() if (
            base_url is None or api_key is None or use_fixtures is None
        ) else None
        self.base_url = (
            base_url if base_url is not None else (cfg.http_base_url if cfg else '')
        ).rstrip('/')
        self.api_key = api_key if api_key is not None else (cfg.api_key if cfg else '')
        self.timeout = timeout
        if use_fixtures is None:
            use_fixtures = bool(cfg.use_fixtures) if cfg else False
        self.use_fixtures = use_fixtures
        self._session = session or requests.Session()

    def _ensure_config(self) -> None:
        if self.use_fixtures:
            return
        if not self.base_url:
            raise XuanpinConfigError(
                '未配置选品 HTTP Base：请在 Admin「选品连接配置」填写，或设 XUANPIN_HTTP_BASE_URL',
            )
        if not self.api_key:
            raise XuanpinConfigError(
                '未配置 MCP API Key：请在 Admin「选品连接配置」填写，或设 XUANPIN_MCP_API_KEY',
            )

    def _headers(self, *, ml_site: str | None = None) -> dict[str, str]:
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json',
        }
        if ml_site:
            headers['X-ML-Site'] = ml_site
        return headers

    def _url(self, path: str) -> str:
        if not path.startswith('/'):
            path = '/' + path
        return urljoin(self.base_url + '/', path.lstrip('/'))

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        ml_site: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_config()
        url = self._url(path)
        try:
            resp = self._session.request(
                method,
                url,
                params=params or {},
                headers=self._headers(ml_site=ml_site),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning('xuanpin listing HTTP error: %s %s → %s', method, url, exc)
            raise XuanpinAPIError(f'选品 Listing API 网络错误: {exc}', status_code=502, code='network') from exc

        if resp.status_code == 401:
            raise XuanpinAPIError('选品 API Key 无效', status_code=401, code='unauthorized')
        if resp.status_code == 403:
            raise XuanpinAPIError('无权限查看该 Listing', status_code=403, code='forbidden')
        if resp.status_code == 404:
            raise XuanpinAPIError('Listing 不存在', status_code=404, code='not_found')
        if resp.status_code >= 400:
            detail = _safe_error_text(resp)
            raise XuanpinAPIError(
                f'选品 Listing API {resp.status_code}: {detail}',
                status_code=502,
                code='upstream_http',
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise XuanpinAPIError('选品返回非 JSON', status_code=502, code='bad_json') from exc

        if isinstance(data, dict) and data.get('success') is False:
            raise XuanpinAPIError(
                str(data.get('error') or '选品返回失败'),
                status_code=400,
                code='upstream_logic',
            )
        return data if isinstance(data, dict) else {'success': True, 'data': data}

    # ---- 契约方法 ----

    def list_product_listings(
        self,
        *,
        status: str | None = None,
        dev_project_id: int | None = None,
        q: str | None = None,
        limit: int = 20,
        offset: int = 0,
        ml_site: str | None = None,
    ) -> dict[str, Any]:
        if self.use_fixtures:
            return fixtures.fixture_list_listings(
                status=status, dev_project_id=dev_project_id, q=q, limit=limit, offset=offset,
            )
        params: dict[str, Any] = {'limit': min(limit, 100), 'offset': offset}
        if status:
            params['status'] = status
        if dev_project_id is not None:
            params['dev_project_id'] = int(dev_project_id)
        if q:
            params['q'] = q
        if ml_site:
            params['ml_site'] = ml_site
        data = self._request('GET', f'{OPEN_PREFIX}/listings/', params=params, ml_site=ml_site)
        items = data.get('items') or data.get('listings') or data.get('results') or []
        return {
            'success': True,
            'count': data.get('count', len(items)),
            'items': items,
            'raw': data,
        }

    def get_product_listing(self, listing_id: int, *, ml_site: str | None = None) -> dict[str, Any]:
        if self.use_fixtures:
            if int(listing_id) != fixtures.SAMPLE_LISTING_ID:
                raise XuanpinAPIError('Listing 不存在（fixture）', status_code=404, code='not_found')
            return {'success': True, 'listing': dict(fixtures.SAMPLE_LISTING)}
        data = self._request(
            'GET', f'{OPEN_PREFIX}/listings/{int(listing_id)}/', ml_site=ml_site,
        )
        listing = data.get('listing') or data
        if 'listing_id' not in listing and data.get('listing_id'):
            listing = data
        return {'success': True, 'listing': listing, 'raw': data}

    def get_content_production(self, listing_id: int, *, ml_site: str | None = None) -> dict[str, Any]:
        if self.use_fixtures:
            if int(listing_id) != fixtures.SAMPLE_LISTING_ID:
                raise XuanpinAPIError('Listing 不存在（fixture）', status_code=404, code='not_found')
            return {
                'success': True,
                'content_production': dict(fixtures.SAMPLE_CONTENT_PRODUCTION),
            }
        data = self._request(
            'GET',
            f'{OPEN_PREFIX}/listings/{int(listing_id)}/content-production/',
            ml_site=ml_site,
        )
        # 契约：无记录时 success + content_production=null
        if 'content_production' in data:
            return {
                'success': True,
                'content_production': data.get('content_production'),
                'raw': data,
            }
        # 兼容：整包即 content_production
        if data.get('listing_id') or data.get('mlb_payload') is not None:
            return {'success': True, 'content_production': data, 'raw': data}
        return {'success': True, 'content_production': None, 'raw': data}

    def list_listing_images(self, listing_id: int, *, ml_site: str | None = None) -> dict[str, Any]:
        if self.use_fixtures:
            if int(listing_id) != fixtures.SAMPLE_LISTING_ID:
                raise XuanpinAPIError('Listing 不存在（fixture）', status_code=404, code='not_found')
            return {'success': True, **fixtures.SAMPLE_IMAGES}
        data = self._request(
            'GET', f'{OPEN_PREFIX}/listings/{int(listing_id)}/images/', ml_site=ml_site,
        )
        images = data.get('images') or []
        return {
            'success': True,
            'listing_id': data.get('listing_id', int(listing_id)),
            'images': images,
            'raw': data,
        }

    def list_listing_faqs(self, listing_id: int, *, ml_site: str | None = None) -> list[dict]:
        if self.use_fixtures:
            if int(listing_id) != fixtures.SAMPLE_LISTING_ID:
                raise XuanpinAPIError('Listing 不存在（fixture）', status_code=404, code='not_found')
            return list(fixtures.SAMPLE_FAQS)
        data = self._request(
            'GET', f'{OPEN_PREFIX}/listings/{int(listing_id)}/faqs/', ml_site=ml_site,
        )
        faqs = data.get('faqs') or data.get('items') or data.get('results') or []
        if isinstance(data, list):
            faqs = data
        return faqs if isinstance(faqs, list) else []


def _safe_error_text(resp: requests.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict):
            return str(data.get('error') or data.get('detail') or resp.text[:200])
    except ValueError:
        pass
    return (resp.text or '')[:200]


def get_default_listing_client() -> XuanpinListingClient:
    cfg = resolve_xuanpin_settings()
    return XuanpinListingClient(
        base_url=cfg.http_base_url,
        api_key=cfg.api_key,
        use_fixtures=cfg.use_fixtures,
    )
