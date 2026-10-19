# -*- coding: utf-8 -*-
"""从选品导入 / 刷新商品上下文。"""
from __future__ import annotations

import logging
import re
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import PlatformListing, ProductMaster

from .exceptions import XuanpinAPIError, XuanpinConfigError
from .settings_resolve import resolve_xuanpin_settings
from .xuanpin_http_client import XuanpinListingClient, get_default_listing_client
from .xuanpin_mcp_client import (
    XuanpinMCPClient,
    get_default_mcp_client,
    summarize_brief_for_cache,
)

logger = logging.getLogger(__name__)

_ML_ITEM_RE = re.compile(r'^(ML[A-Z])(\d+)$', re.IGNORECASE)


def fetch_xuanpin_bundle(
    *,
    listing_id: int,
    ml_site: str | None = None,
    listing_client: XuanpinListingClient | None = None,
    mcp_client: XuanpinMCPClient | None = None,
    include_brief: bool = True,
) -> dict[str, Any]:
    """拉取 Listing + 内容生产 + 图集 + FAQ +（可选）简报摘要。"""
    listing_client = listing_client or get_default_listing_client()
    mcp_client = mcp_client or get_default_mcp_client()

    listing_resp = listing_client.get_product_listing(listing_id, ml_site=ml_site)
    listing = listing_resp.get('listing') or {}
    if not listing.get('listing_id'):
        listing['listing_id'] = int(listing_id)

    content = None
    try:
        content = listing_client.get_content_production(listing_id, ml_site=ml_site).get(
            'content_production',
        )
    except XuanpinAPIError as exc:
        if exc.status_code != 404:
            raise
        content = None

    images_payload = listing_client.list_listing_images(listing_id, ml_site=ml_site)
    images = images_payload.get('images') or []

    faqs: list[dict] = []
    try:
        faqs = listing_client.list_listing_faqs(listing_id, ml_site=ml_site) or []
    except XuanpinAPIError as exc:
        # FAQ 可选：上游未实现时不阻断导入
        if exc.status_code not in (404, 501) and exc.code != 'upstream_http':
            logger.warning('list_listing_faqs failed: %s', exc)
        faqs = []

    brief_summary: dict[str, Any] = {}
    brief_error = ''
    # 优先用 Listing 详情里的 brief_summary（选品只读 API 已内嵌）
    embedded = listing.get('brief_summary')
    if include_brief and isinstance(embedded, dict) and embedded:
        brief_summary = {
            'task_id': embedded.get('stakeholder_brief_id') or listing.get('stakeholder_brief_id'),
            'title': embedded.get('name') or '',
            'report_excerpt': embedded.get('report_excerpt') or '',
            'has_report': embedded.get('has_report'),
            'has_listing_pack': embedded.get('has_listing_pack'),
            'has_image_brief_pack': embedded.get('has_image_brief_pack'),
            'listing_pack_summary': embedded.get('listing_pack_preview') or {},
            'image_brief_pack_keys': [],
            'listing_pack_keys': list((embedded.get('listing_pack_preview') or {}).keys()),
            'source': 'listing_detail',
        }
    brief_id = listing.get('stakeholder_brief_id')
    if include_brief and brief_id and not brief_summary.get('report_excerpt') and not brief_summary.get('listing_pack_summary'):
        try:
            raw_brief = mcp_client.get_stakeholder_brief(int(brief_id), ml_site=ml_site)
            if raw_brief.get('success') is False:
                brief_error = str(raw_brief.get('error') or '简报拉取失败')
            else:
                brief_summary = summarize_brief_for_cache(raw_brief)
                brief_summary['source'] = 'mcp'
        except (XuanpinAPIError, XuanpinConfigError) as exc:
            brief_error = str(exc)
            logger.info('brief enrichment skipped: %s', exc)

    return {
        'listing': listing,
        'content_production': content,
        'images': images,
        'faqs': faqs,
        'brief_summary': brief_summary,
        'brief_error': brief_error,
        'ml_site': ml_site or 'MLB',
        'fetched_at': timezone.now().isoformat(),
    }


def build_context_json(bundle: dict[str, Any]) -> dict[str, Any]:
    listing = bundle.get('listing') or {}
    images = bundle.get('images') or []
    image_urls = [
        (img.get('url') if isinstance(img, dict) else None)
        for img in images
    ]
    image_urls = [u for u in image_urls if u]
    if not image_urls:
        image_urls = list(listing.get('listing_image_urls') or []) + list(
            listing.get('gallery_urls') or [],
        )

    return {
        'listing_id': listing.get('listing_id'),
        'title': listing.get('title') or '',
        'listing_title': listing.get('listing_title') or '',
        'status': listing.get('status') or '',
        'dev_project_id': listing.get('dev_project_id'),
        'platform_product_id': listing.get('platform_product_id'),
        'platform_sku': listing.get('platform_sku') or '',
        'stakeholder_brief_id': listing.get('stakeholder_brief_id'),
        'listing_bullets': listing.get('listing_bullets') or [],
        'listing_characteristics': listing.get('listing_characteristics') or {},
        'listing_description': listing.get('listing_description') or '',
        'image_urls': image_urls,
        'images': images,
        'faqs': bundle.get('faqs') or [],
        'content_production': _thin_content(bundle.get('content_production')),
        'brief': bundle.get('brief_summary') or {},
        'brief_error': bundle.get('brief_error') or '',
        'ml_site': bundle.get('ml_site') or 'MLB',
        'fetched_at': bundle.get('fetched_at'),
    }


def _thin_content(content: dict | None) -> dict | None:
    if not content:
        return None
    return {
        'listing_id': content.get('listing_id'),
        'status': content.get('status'),
        'updated_at': content.get('updated_at'),
        'has_mlb_payload': bool(content.get('mlb_payload')),
        'has_shopee_payload': bool(content.get('shopee_payload')),
    }


def _resolve_listing_id(
    *,
    listing_id: int | None,
    dev_project_id: int | None,
    ml_site: str | None,
    listing_client: XuanpinListingClient,
) -> int:
    if listing_id:
        return int(listing_id)
    if not dev_project_id:
        raise XuanpinAPIError(
            '请提供 listing_id，或提供 dev_project_id 以从选品列表解析',
            status_code=400,
            code='bad_request',
        )
    listed = listing_client.list_product_listings(
        dev_project_id=int(dev_project_id),
        limit=20,
        ml_site=ml_site,
    )
    items = listed.get('items') or []
    if not items:
        raise XuanpinAPIError(
            f'dev_project_id={dev_project_id} 下未找到 ProductListing',
            status_code=404,
            code='not_found',
        )
    # 优先 pending，否则取第一条
    pending = [i for i in items if (i.get('status') or '') == 'pending']
    chosen = (pending or items)[0]
    lid = chosen.get('listing_id')
    if not lid:
        raise XuanpinAPIError('选品列表项缺少 listing_id', status_code=502, code='bad_payload')
    return int(lid)


def _apply_bundle_to_product(
    product: ProductMaster,
    bundle: dict[str, Any],
    *,
    touch_identity: bool,
) -> ProductMaster:
    listing = bundle['listing']
    context = build_context_json(bundle)
    cover = ''
    urls = context.get('image_urls') or []
    if urls:
        cover = urls[0]
    elif listing.get('primary_image_url'):
        cover = listing['primary_image_url']

    if touch_identity:
        name = (
            listing.get('title')
            or listing.get('listing_title')
            or product.name
            or f"Listing#{listing.get('listing_id')}"
        )
        product.name = name
        sku = (listing.get('platform_sku') or product.internal_sku or '').strip()
        if sku:
            product.internal_sku = sku[:100]
        if cover:
            product.cover_image_url = cover[:2000]
        product.xuanpin_listing_id = int(listing['listing_id'])
        if listing.get('dev_project_id'):
            product.xuanpin_dev_project_id = int(listing['dev_project_id'])

    product.xuanpin_context_json = context
    product.xuanpin_fetched_at = timezone.now()
    product.save()
    return product


def _maybe_upsert_platform_listing(
    product: ProductMaster,
    bundle: dict[str, Any],
    *,
    item_id: str | None = None,
) -> PlatformListing | None:
    """若能解析美客多 Item ID，则创建/更新 platform_listing。"""
    listing = bundle.get('listing') or {}
    ml_site = (bundle.get('ml_site') or 'MLB').upper()
    raw = (item_id or listing.get('platform_sku') or '').strip()
    if not raw:
        return None

    matched = _ML_ITEM_RE.match(raw.replace('-', '').replace('_', ''))
    if matched:
        site = matched.group(1).upper()
        num = matched.group(2)
        resolved_item = f'{site}{num}'
        ml_site = site
    elif raw.upper().startswith('ML') and raw[2:].isdigit():
        resolved_item = raw.upper()
        ml_site = raw[:3].upper()
    elif item_id:
        resolved_item = item_id.strip()
    else:
        return None

    pl, _created = PlatformListing.objects.update_or_create(
        platform=PlatformListing.PLATFORM_ML,
        ml_site=ml_site,
        item_id=resolved_item,
        defaults={
            'product': product,
            'sync_status': 'imported',
        },
    )
    # 若已绑到其他商品，以本次导入为准（MVP）
    if pl.product_id != product.id:
        pl.product = product
        pl.save(update_fields=['product', 'updated_at'])
    return pl


@transaction.atomic
def import_from_xuanpin(
    *,
    listing_id: int | None = None,
    dev_project_id: int | None = None,
    ml_site: str | None = None,
    item_id: str | None = None,
    listing_client: XuanpinListingClient | None = None,
    mcp_client: XuanpinMCPClient | None = None,
) -> dict[str, Any]:
    """导入或按 listing_id 幂等更新主档。"""
    listing_client = listing_client or get_default_listing_client()
    if not ml_site:
        ml_site = resolve_xuanpin_settings().default_ml_site or 'MLB'
    resolved_id = _resolve_listing_id(
        listing_id=listing_id,
        dev_project_id=dev_project_id,
        ml_site=ml_site,
        listing_client=listing_client,
    )
    bundle = fetch_xuanpin_bundle(
        listing_id=resolved_id,
        ml_site=ml_site,
        listing_client=listing_client,
        mcp_client=mcp_client,
    )

    product = ProductMaster.objects.filter(xuanpin_listing_id=resolved_id).first()
    created = False
    if not product:
        product = ProductMaster(name=f'Listing#{resolved_id}', status='active')
        created = True

    _apply_bundle_to_product(product, bundle, touch_identity=True)
    platform_listing = _maybe_upsert_platform_listing(product, bundle, item_id=item_id)

    return {
        'created': created,
        'product': product,
        'platform_listing': platform_listing,
        'bundle': bundle,
    }


@transaction.atomic
def refresh_xuanpin_context(
    product: ProductMaster,
    *,
    ml_site: str | None = None,
    listing_client: XuanpinListingClient | None = None,
    mcp_client: XuanpinMCPClient | None = None,
) -> dict[str, Any]:
    """刷新选品上下文缓存；不覆盖已审核素材版本。"""
    if not product.xuanpin_listing_id:
        raise XuanpinAPIError(
            '该商品未绑定 xuanpin_listing_id，无法刷新',
            status_code=400,
            code='bad_request',
        )
    site = ml_site or (product.xuanpin_context_json or {}).get('ml_site') or 'MLB'
    bundle = fetch_xuanpin_bundle(
        listing_id=int(product.xuanpin_listing_id),
        ml_site=site,
        listing_client=listing_client,
        mcp_client=mcp_client,
    )
    # 刷新：更新上下文与封面/名称镜像，不碰 creative / publish
    _apply_bundle_to_product(product, bundle, touch_identity=True)
    product.refresh_from_db()
    return {'product': product, 'bundle': bundle}


def serialize_product(product: ProductMaster, *, include_context: bool = True) -> dict[str, Any]:
    ctx = product.xuanpin_context_json or {}
    payload: dict[str, Any] = {
        'id': product.id,
        'name': product.name,
        'internal_sku': product.internal_sku,
        'xuanpin_listing_id': product.xuanpin_listing_id,
        'xuanpin_dev_project_id': product.xuanpin_dev_project_id,
        'cover_image_url': product.cover_image_url,
        'status': product.status,
        'xuanpin_fetched_at': product.xuanpin_fetched_at.isoformat() if product.xuanpin_fetched_at else None,
        'updated_at': product.updated_at.isoformat() if product.updated_at else None,
        'platform_listings': [
            {
                'id': pl.id,
                'platform': pl.platform,
                'ml_site': pl.ml_site,
                'item_id': pl.item_id,
                'permalink': pl.permalink,
                'sync_status': pl.sync_status,
                'current_version_id': pl.current_version_id,
            }
            for pl in product.platform_listings.all()
        ],
    }
    if include_context:
        payload['xuanpin_context'] = {
            'title': ctx.get('title'),
            'listing_title': ctx.get('listing_title'),
            'listing_bullets': ctx.get('listing_bullets') or [],
            'listing_description': ctx.get('listing_description') or '',
            'image_urls': ctx.get('image_urls') or [],
            'brief': ctx.get('brief') or {},
            'brief_error': ctx.get('brief_error') or '',
            'faqs_count': len(ctx.get('faqs') or []),
            'content_production': ctx.get('content_production'),
            'platform_sku': ctx.get('platform_sku') or '',
            'ml_site': ctx.get('ml_site') or 'MLB',
            'fetched_at': ctx.get('fetched_at'),
        }
    return payload
