# -*- coding: utf-8 -*-
"""Workbench API：W1 导入 / 刷新 / 商品详情。"""
from __future__ import annotations

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.catalog.models import ProductMaster
from apps.catalog.services import (
    XuanpinAPIError,
    XuanpinConfigError,
    import_from_xuanpin,
    refresh_xuanpin_context,
    resolve_xuanpin_settings,
    serialize_product,
)
from apps.catalog.services.settings_resolve import mask_api_key


logger = logging.getLogger(__name__)


def _parse_json(request) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise XuanpinAPIError('无效 JSON', status_code=400, code='bad_json')
    return data if isinstance(data, dict) else {}


def _error_response(exc: Exception) -> JsonResponse:
    if isinstance(exc, XuanpinConfigError):
        return JsonResponse(
            {'success': False, 'error': str(exc), 'code': 'config'},
            status=503,
        )
    if isinstance(exc, XuanpinAPIError):
        return JsonResponse(exc.to_dict(), status=exc.status_code)
    logger.exception('workbench unexpected error')
    return JsonResponse(
        {'success': False, 'error': '服务器内部错误', 'code': 'internal'},
        status=500,
    )


@require_GET
def mvp_meta(_request):
    cfg = resolve_xuanpin_settings()
    return JsonResponse({
        'success': True,
        'phase': 'MVP',
        'docs': [
            'docs/PRD-MVP.md',
            'docs/ARCHITECTURE.md',
            'docs/API-CONTRACTS.md',
            'docs/TASKS-XUANPIN-LISTING-READ-API.md',
        ],
        'w1': {
            'import_from_xuanpin': 'ready',
            'refresh_xuanpin': 'ready',
            'xuanpin_config_source': cfg.source,
            'xuanpin_use_fixtures': cfg.use_fixtures,
            'xuanpin_http_configured': bool(cfg.http_base_url),
            'xuanpin_mcp_configured': bool(cfg.mcp_base_url and cfg.api_key),
            'xuanpin_api_key_masked': mask_api_key(cfg.api_key),
            'xuanpin_http_base_url': cfg.http_base_url,
            'default_ml_site': cfg.default_ml_site,
        },
        'pending': [
            'xuanpin listing read API 联调（Admin 配 Key 后 import listing_id）',
            'AI generate / review (W2)',
            'meli adapter publish/rollback (W3)',
        ],
    })


@login_required
@require_GET
def product_list(_request):
    items = [
        {
            'id': p.id,
            'name': p.name,
            'internal_sku': p.internal_sku,
            'xuanpin_listing_id': p.xuanpin_listing_id,
            'cover_image_url': p.cover_image_url,
            'xuanpin_fetched_at': (
                p.xuanpin_fetched_at.isoformat() if p.xuanpin_fetched_at else None
            ),
            'updated_at': p.updated_at.isoformat(),
        }
        for p in ProductMaster.objects.all()[:100]
    ]
    return JsonResponse({'success': True, 'count': len(items), 'items': items})


@login_required
@require_GET
def product_detail(_request, product_id: int):
    product = get_object_or_404(
        ProductMaster.objects.prefetch_related('platform_listings'),
        pk=product_id,
    )
    return JsonResponse({
        'success': True,
        'product': serialize_product(product),
    })


@login_required
@require_POST
def import_from_xuanpin_view(request):
    try:
        data = _parse_json(request)
        listing_id = data.get('listing_id') or data.get('product_listing_id')
        dev_project_id = data.get('dev_project_id')
        ml_site = (data.get('ml_site') or '').strip() or None
        item_id = (data.get('item_id') or '').strip() or None

        if listing_id is not None:
            listing_id = int(listing_id)
        if dev_project_id is not None:
            dev_project_id = int(dev_project_id)

        result = import_from_xuanpin(
            listing_id=listing_id,
            dev_project_id=dev_project_id,
            ml_site=ml_site,
            item_id=item_id,
        )
        product = result['product']
        pl = result.get('platform_listing')
        return JsonResponse({
            'success': True,
            'created': result['created'],
            'product': serialize_product(product),
            'platform_listing_id': pl.id if pl else None,
        })
    except (TypeError, ValueError):
        return JsonResponse(
            {'success': False, 'error': 'listing_id / dev_project_id 须为整数', 'code': 'bad_request'},
            status=400,
        )
    except (XuanpinAPIError, XuanpinConfigError) as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc)


@login_required
@require_http_methods(['POST'])
def refresh_xuanpin_view(request, product_id: int):
    try:
        data = _parse_json(request)
        ml_site = (data.get('ml_site') or '').strip() or None
        product = get_object_or_404(ProductMaster, pk=product_id)
        result = refresh_xuanpin_context(product, ml_site=ml_site)
        return JsonResponse({
            'success': True,
            'product': serialize_product(result['product']),
        })
    except (XuanpinAPIError, XuanpinConfigError) as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc)
