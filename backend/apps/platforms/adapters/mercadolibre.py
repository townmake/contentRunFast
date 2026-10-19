# -*- coding: utf-8 -*-
"""美客多 Adapter：读 Item、上传图片、整表更新 pictures。"""
from __future__ import annotations

import logging
from typing import Any

import requests

from apps.platforms.exceptions import PlatformConfigError, PlatformError

from .base import PlatformAdapter

logger = logging.getLogger(__name__)

API_BASE = 'https://api.mercadolibre.com'
DEFAULT_TIMEOUT = 45


class MercadoLibreAdapter(PlatformAdapter):
    platform = 'mercadolibre'

    def __init__(
        self,
        *,
        access_token: str = '',
        site_id: str = 'MLB',
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
        dry_run: bool = False,
    ):
        self.access_token = (access_token or '').strip()
        self.site_id = (site_id or 'MLB').upper()
        self.timeout = timeout
        self._session = session or requests.Session()
        self.dry_run = dry_run
        self._dry_seq = 0

    def capabilities(self) -> dict[str, str]:
        if self.dry_run:
            return {
                'read_product': 'supported',
                'write_images': 'supported',
                'read_ads': 'unavailable',
                'mode': 'dry_run',
            }
        if not self.access_token:
            return {
                'read_product': 'needs_permission',
                'write_images': 'needs_permission',
                'read_ads': 'needs_permission',
            }
        return {
            'read_product': 'supported',
            'write_images': 'supported',
            'read_ads': 'needs_permission',
        }

    def _headers(self, *, json_body: bool = False) -> dict[str, str]:
        if not self.access_token and not self.dry_run:
            raise PlatformConfigError('未配置美客多 Access Token（MELI_ACCESS_TOKEN 或平台账号 token_ref）')
        headers = {
            'Authorization': f'Bearer {self.access_token or "dry-run"}',
            'Accept': 'application/json',
        }
        if json_body:
            headers['Content-Type'] = 'application/json'
        return headers

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = path if path.startswith('http') else f'{API_BASE}{path}'
        try:
            resp = self._session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise PlatformError(f'美客多网络错误: {exc}', code='network') from exc

        if resp.status_code == 401:
            raise PlatformError('美客多 Token 无效或过期', code='unauthorized', status_code=401)
        if resp.status_code == 403:
            raise PlatformError('美客多无权限（检查 scope / 店铺）', code='forbidden', status_code=403)
        if resp.status_code == 404:
            raise PlatformError('美客多资源不存在', code='not_found', status_code=404)
        if resp.status_code >= 400:
            detail = (resp.text or '')[:400]
            raise PlatformError(f'美客多 HTTP {resp.status_code}: {detail}', code='upstream_http')

        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError as exc:
            raise PlatformError('美客多返回非 JSON', code='bad_json') from exc

    def get_product(self, item_ref: str) -> dict[str, Any]:
        item_id = (item_ref or '').strip().upper()
        if not item_id:
            raise PlatformError('item_id 为空', code='bad_request', status_code=400)

        if self.dry_run:
            return {
                'id': item_id,
                'title': f'[dry-run] {item_id}',
                'status': 'active',
                'permalink': f'https://produto.mercadolivre.com.br/{item_id}',
                'pictures': [
                    {
                        'id': f'DRY-{item_id}-1',
                        'url': 'https://httpbin.org/image/jpeg',
                        'secure_url': 'https://httpbin.org/image/jpeg',
                    },
                    {
                        'id': f'DRY-{item_id}-2',
                        'url': 'https://httpbin.org/image/png',
                        'secure_url': 'https://httpbin.org/image/png',
                    },
                ],
                'dry_run': True,
            }

        data = self._request('GET', f'/items/{item_id}', headers=self._headers())
        pictures = data.get('pictures') or []
        return {
            'id': data.get('id') or item_id,
            'title': data.get('title') or '',
            'status': data.get('status') or '',
            'permalink': data.get('permalink') or '',
            'pictures': pictures,
            'raw': {
                'price': data.get('price'),
                'available_quantity': data.get('available_quantity'),
                'sold_quantity': data.get('sold_quantity'),
                'category_id': data.get('category_id'),
            },
        }

    def upload_asset(self, file_bytes: bytes, *, filename: str = 'image.jpg') -> str:
        if not file_bytes:
            raise PlatformError('上传图片内容为空', code='bad_request', status_code=400)

        if self.dry_run:
            self._dry_seq += 1
            return f'DRY-UP-{self._dry_seq:04d}'

        files = {'file': (filename, file_bytes, _guess_content_type(filename))}
        data = self._request(
            'POST',
            '/pictures/items/upload',
            headers=self._headers(),
            files=files,
        )
        picture_id = data.get('id') or ''
        if not picture_id:
            raise PlatformError(f'上传成功但未返回 picture id: {data!r}', code='bad_payload')
        return str(picture_id)

    def update_listing_images(self, item_ref: str, image_ids_ordered: list[str]) -> dict[str, Any]:
        """
        整表写回 pictures。
        image_ids_ordered 元素可以是：
        - 已有 picture id
        - http(s) URL（将以 source 形式提交）
        """
        item_id = (item_ref or '').strip().upper()
        if not item_id:
            raise PlatformError('item_id 为空', code='bad_request', status_code=400)
        if not image_ids_ordered:
            raise PlatformError('图片列表不能为空', code='bad_request', status_code=400)

        pictures_payload = []
        for ref in image_ids_ordered:
            ref = (ref or '').strip()
            if not ref:
                continue
            if ref.startswith('http://') or ref.startswith('https://'):
                pictures_payload.append({'source': ref})
            else:
                pictures_payload.append({'id': ref})

        if not pictures_payload:
            raise PlatformError('有效图片引用为空', code='bad_request', status_code=400)

        if self.dry_run:
            return {
                'id': item_id,
                'pictures': [
                    {
                        'id': p.get('id') or f'DRY-SRC-{i}',
                        'source': p.get('source'),
                        'url': p.get('source') or f'https://httpbin.org/image/jpeg?i={i}',
                        'secure_url': p.get('source') or f'https://httpbin.org/image/jpeg?i={i}',
                    }
                    for i, p in enumerate(pictures_payload)
                ],
                'dry_run': True,
            }

        data = self._request(
            'PUT',
            f'/items/{item_id}',
            headers=self._headers(json_body=True),
            json={'pictures': pictures_payload},
        )
        return {
            'id': data.get('id') or item_id,
            'pictures': data.get('pictures') or [],
            'status': data.get('status'),
        }


def _guess_content_type(filename: str) -> str:
    name = (filename or '').lower()
    if name.endswith('.png'):
        return 'image/png'
    if name.endswith('.webp'):
        return 'image/webp'
    if name.endswith('.gif'):
        return 'image/gif'
    return 'image/jpeg'


def snapshot_pictures(product_dto: dict) -> dict:
    """压缩入库的 before/after 快照。"""
    pics = product_dto.get('pictures') or []
    return {
        'id': product_dto.get('id'),
        'title': product_dto.get('title'),
        'status': product_dto.get('status'),
        'permalink': product_dto.get('permalink'),
        'dry_run': bool(product_dto.get('dry_run')),
        'pictures': [
            {
                'id': p.get('id'),
                'url': p.get('secure_url') or p.get('url') or p.get('source'),
                'size': p.get('size'),
                'max_size': p.get('max_size'),
            }
            for p in pics
            if isinstance(p, dict)
        ],
    }
