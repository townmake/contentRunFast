# -*- coding: utf-8 -*-
"""发布编排：读完整 pictures → 上传/组装 → 整表写回 → 校验 → 留痕；支持回滚。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import PlatformListing, ProductMaster
from apps.creative.models import CreativeVersion
from apps.platforms.adapters.mercadolibre import snapshot_pictures
from apps.platforms.exceptions import PlatformConfigError, PlatformError
from apps.platforms.services.factory import get_meli_adapter
from apps.publish.models import PublicationHistory

logger = logging.getLogger(__name__)


class PublishError(Exception):
    def __init__(self, message: str, *, code: str = 'publish_error'):
        super().__init__(message)
        self.message = message
        self.code = code


def preflight_publish(
    *,
    platform_listing: PlatformListing,
    version: CreativeVersion,
    dry_run: bool = False,
) -> dict[str, Any]:
    checks = []

    def add(ok: bool, name: str, detail: str = ''):
        checks.append({'ok': ok, 'name': name, 'detail': detail})

    add(
        version.review_status == CreativeVersion.REVIEW_APPROVED,
        'version_approved',
        f'status={version.review_status}',
    )
    add(bool(platform_listing.item_id), 'has_item_id', platform_listing.item_id or '空')
    add(platform_listing.platform == PlatformListing.PLATFORM_ML, 'platform_meli', platform_listing.platform)

    image_uris = _version_image_uris(version)
    add(len(image_uris) >= 1, 'images_non_empty', f'count={len(image_uris)}')

    caps = {}
    try:
        adapter = get_meli_adapter(
            preferred_site=platform_listing.ml_site,
            account=platform_listing.shop_account,
            force_dry_run=dry_run,
        )
        caps = adapter.capabilities()
        add(caps.get('write_images') == 'supported', 'write_images_capability', str(caps))
        add(caps.get('read_product') == 'supported', 'read_product_capability', str(caps))
    except PlatformConfigError as exc:
        add(False, 'adapter_config', str(exc))
        adapter = None

    snapshot = None
    if adapter is not None and all(c['ok'] for c in checks if c['name'] != 'write_images_capability'):
        try:
            product_dto = adapter.get_product(platform_listing.item_id)
            snapshot = snapshot_pictures(product_dto)
            add(True, 'fetch_current_pictures', f"count={len(snapshot.get('pictures') or [])}")
        except PlatformError as exc:
            add(False, 'fetch_current_pictures', str(exc))

    ok = all(c['ok'] for c in checks)
    return {
        'ok': ok,
        'checks': checks,
        'image_uris': image_uris,
        'snapshot_before': snapshot,
        'capabilities': caps,
        'dry_run': dry_run,
    }


def _version_image_uris(version: CreativeVersion) -> list[str]:
    assets = list(version.assets.all())
    uris = [a.uri for a in assets if a.uri]
    if not uris:
        uris = list((version.payload or {}).get('image_uris') or [])
    return [u for u in uris if u]


def _load_bytes_from_uri(uri: str) -> tuple[bytes, str]:
    """返回 (bytes, filename)。本地 media 或远程 URL。"""
    media_url = (settings.MEDIA_URL or '/media/').rstrip('/') + '/'
    if uri.startswith(media_url) or uri.startswith('/media/'):
        rel = uri.split('/media/', 1)[-1]
        path = Path(settings.MEDIA_ROOT) / rel
        if not path.exists():
            raise PublishError(f'本地媒体不存在: {uri}', code='media_missing')
        return path.read_bytes(), path.name

    if uri.startswith('http://') or uri.startswith('https://'):
        # 公网 URL 可直接 source 提交，此处仅在需要 multipart 时下载
        try:
            resp = requests.get(uri, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise PublishError(f'下载图片失败: {uri} ({exc})', code='download_failed') from exc
        name = Path(urlparse(uri).path).name or 'image.jpg'
        return resp.content, name

    # 相对路径当 media
    path = Path(settings.MEDIA_ROOT) / uri.lstrip('/')
    if path.exists():
        return path.read_bytes(), path.name
    raise PublishError(f'无法解析图片 URI: {uri}', code='bad_uri')


@transaction.atomic
def publish_version_images(
    *,
    platform_listing: PlatformListing,
    version: CreativeVersion,
    operator=None,
    dry_run: bool = False,
    strategy: str = 'replace_all',
) -> PublicationHistory:
    """
    strategy:
      - replace_all: 用版本图整表替换
      - replace_main: 版本图放主图位，其后保留原图（去重）
    """
    if version.product_id != platform_listing.product_id:
        raise PublishError('版本与平台链接不属于同一商品', code='mismatch')

    pre = preflight_publish(
        platform_listing=platform_listing,
        version=version,
        dry_run=dry_run,
    )
    if not pre['ok']:
        failed = [c for c in pre['checks'] if not c['ok']]
        raise PublishError(
            '发布前检查未通过: ' + '; '.join(f"{c['name']}={c['detail']}" for c in failed),
            code='preflight',
        )

    history = PublicationHistory.objects.create(
        platform_listing=platform_listing,
        version=version,
        status=PublicationHistory.STATUS_QUEUED,
        operator=operator if getattr(operator, 'pk', None) else None,
        snapshot_before_json=pre.get('snapshot_before') or {},
    )

    adapter = get_meli_adapter(
        preferred_site=platform_listing.ml_site,
        account=platform_listing.shop_account,
        force_dry_run=dry_run,
    )

    try:
        # 再读一次，确保 snapshot 最新
        history.status = 'uploading'
        history.save(update_fields=['status'])

        current = adapter.get_product(platform_listing.item_id)
        before = snapshot_pictures(current)
        history.snapshot_before_json = before
        history.save(update_fields=['snapshot_before_json'])

        image_uris = pre['image_uris']
        # 本地 media 必须 upload；公网 URL 用 source
        new_refs: list[str] = []
        for uri in image_uris:
            if uri.startswith('http://') or uri.startswith('https://'):
                new_refs.append(uri)
            else:
                raw, filename = _load_bytes_from_uri(uri)
                new_refs.append(adapter.upload_asset(raw, filename=filename))

        if strategy == 'replace_main':
            old_ids = [p.get('id') for p in (before.get('pictures') or []) if p.get('id')]
            # 主图用新图，其余旧图跟在后面（排除与新 id 重复）
            ordered = list(new_refs) + [i for i in old_ids if i not in new_refs]
        else:
            ordered = list(new_refs)

        history.status = 'updating'
        history.save(update_fields=['status'])
        adapter.update_listing_images(platform_listing.item_id, ordered)

        history.status = 'verifying'
        history.save(update_fields=['status'])
        after_dto = adapter.get_product(platform_listing.item_id)
        after = snapshot_pictures(after_dto)

        history.snapshot_after_json = after
        history.status = PublicationHistory.STATUS_SUCCEEDED
        history.published_at = timezone.now()
        history.error = ''
        history.save()

        platform_listing.current_version = version
        platform_listing.sync_status = 'published_dry' if adapter.dry_run else 'published'
        if after_dto.get('permalink'):
            platform_listing.permalink = after_dto['permalink'][:2000]
        platform_listing.save(update_fields=[
            'current_version', 'sync_status', 'permalink', 'updated_at',
        ])

        version.review_status = CreativeVersion.REVIEW_PUBLISHED
        version.role = CreativeVersion.ROLE_CURRENT
        version.save(update_fields=['review_status', 'role', 'updated_at'])

        return history
    except Exception as exc:
        logger.exception('publish failed')
        history.status = PublicationHistory.STATUS_FAILED
        history.error = str(exc)[:2000]
        history.save(update_fields=['status', 'error'])
        raise PublishError(str(exc), code='publish_failed') from exc


@transaction.atomic
def rollback_publication(
    *,
    history: PublicationHistory,
    operator=None,
    dry_run: bool = False,
) -> PublicationHistory:
    before = history.snapshot_before_json or {}
    pics = before.get('pictures') or []
    ids = [p.get('id') for p in pics if isinstance(p, dict) and p.get('id')]
    if not ids:
        raise PublishError('该历史无 snapshot_before.pictures，无法回滚', code='no_snapshot')

    platform_listing = history.platform_listing
    adapter = get_meli_adapter(
        preferred_site=platform_listing.ml_site,
        account=platform_listing.shop_account,
        force_dry_run=dry_run or bool(before.get('dry_run')),
    )

    rb = PublicationHistory.objects.create(
        platform_listing=platform_listing,
        version=history.version,
        status='rollback_queued',
        operator=operator if getattr(operator, 'pk', None) else None,
        snapshot_before_json=snapshot_pictures(adapter.get_product(platform_listing.item_id)),
    )
    try:
        rb.status = 'updating'
        rb.save(update_fields=['status'])
        adapter.update_listing_images(platform_listing.item_id, ids)
        after = snapshot_pictures(adapter.get_product(platform_listing.item_id))
        rb.snapshot_after_json = after
        rb.status = PublicationHistory.STATUS_ROLLED_BACK
        rb.published_at = timezone.now()
        rb.save()

        history.status = PublicationHistory.STATUS_ROLLED_BACK
        history.save(update_fields=['status'])

        # 回滚后清空 current_version 标记（或保留历史 version）
        platform_listing.sync_status = 'rolled_back'
        platform_listing.save(update_fields=['sync_status', 'updated_at'])
        return rb
    except Exception as exc:
        rb.status = PublicationHistory.STATUS_FAILED
        rb.error = str(exc)[:2000]
        rb.save(update_fields=['status', 'error'])
        raise PublishError(str(exc), code='rollback_failed') from exc


def ensure_platform_listing(
    product: ProductMaster,
    *,
    item_id: str,
    ml_site: str = 'MLB',
) -> PlatformListing:
    item_id = (item_id or '').strip().upper().replace('-', '')
    if not item_id:
        raise PublishError('item_id 不能为空', code='bad_request')
    ml_site = (ml_site or 'MLB').upper()
    pl, _ = PlatformListing.objects.update_or_create(
        platform=PlatformListing.PLATFORM_ML,
        ml_site=ml_site,
        item_id=item_id,
        defaults={'product': product, 'sync_status': 'linked'},
    )
    if pl.product_id != product.id:
        pl.product = product
        pl.save(update_fields=['product', 'updated_at'])
    return pl


def list_publications(product: ProductMaster) -> list[PublicationHistory]:
    listing_ids = product.platform_listings.values_list('id', flat=True)
    return list(
        PublicationHistory.objects
        .filter(platform_listing_id__in=listing_ids)
        .select_related('platform_listing', 'version', 'operator')
        .order_by('-created_at')[:50]
    )
