# -*- coding: utf-8 -*-
"""工作台页面：商品列表 / 选品导入 / 详情 Tabs（W1+W2）。"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

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
from apps.catalog.services.xuanpin_http_client import XuanpinListingClient
from apps.creative.models import CreativeVersion
from apps.creative.services import (
    create_candidates_from_context,
    create_version_from_uploads,
    list_versions,
    review_version,
)
from apps.platforms.exceptions import PlatformConfigError, PlatformError
from apps.platforms.services.credentials import meli_dry_run_enabled, resolve_meli_credentials
from apps.platforms.services.factory import get_meli_adapter
from apps.publish.models import PublicationHistory
from apps.publish.services import (
    PublishError,
    ensure_platform_listing,
    list_publications,
    preflight_publish,
    publish_version_images,
    rollback_publication,
)

logger = logging.getLogger(__name__)

VALID_TABS = ('context', 'generate', 'assets', 'publish', 'history', 'analysis')


def _cfg_context():
    cfg = resolve_xuanpin_settings()
    key_ok = bool(cfg.api_key) and cfg.api_key not in ('mcp_your_key_here',) and not str(
        cfg.api_key,
    ).endswith('your_key_here')
    return {
        'xuanpin_cfg': cfg,
        'xuanpin_key_masked': mask_api_key(cfg.api_key),
        'xuanpin_key_ready': key_ok or cfg.use_fixtures,
        'settings_admin_url': '/admin/catalog/xuanpinconnectionsettings/',
    }


def _fetch_xuanpin_listings(*, status: str | None, q: str | None, ml_site: str | None):
    cfg = resolve_xuanpin_settings()
    client = XuanpinListingClient(
        base_url=cfg.http_base_url,
        api_key=cfg.api_key,
        use_fixtures=cfg.use_fixtures,
    )
    data = client.list_product_listings(
        status=status or None,
        q=q or None,
        limit=50,
        offset=0,
        ml_site=ml_site or cfg.default_ml_site,
    )
    return data.get('items') or [], data.get('count', 0)


@login_required
@require_http_methods(['GET'])
def products_list(request):
    q = (request.GET.get('q') or '').strip()
    mapped = (request.GET.get('mapped') or '').strip()
    qs = (
        ProductMaster.objects
        .annotate(
            pending_count=Count(
                'versions',
                filter=Q(versions__review_status=CreativeVersion.REVIEW_PENDING),
            ),
        )
        .order_by('-updated_at')
    )
    if q:
        qs = qs.filter(name__icontains=q)
    if mapped == '1':
        qs = qs.filter(platform_listings__isnull=False).distinct()
    elif mapped == '0':
        qs = qs.filter(platform_listings__isnull=True)

    return render(request, 'products/list.html', {
        **_cfg_context(),
        'nav_active': 'products',
        'products': list(qs[:100]),
        'filters': {'q': q, 'mapped': mapped},
    })


@login_required
@require_http_methods(['GET', 'POST'])
def workbench_home(request):
    error = ''
    cfg = resolve_xuanpin_settings()

    if request.method == 'POST':
        listing_id = (request.POST.get('listing_id') or '').strip()
        dev_project_id = (request.POST.get('dev_project_id') or '').strip()
        ml_site = (request.POST.get('ml_site') or '').strip() or None
        try:
            result = import_from_xuanpin(
                listing_id=int(listing_id) if listing_id else None,
                dev_project_id=int(dev_project_id) if dev_project_id else None,
                ml_site=ml_site,
            )
            product = result['product']
            verb = '新建' if result['created'] else '更新'
            messages.success(request, f'{verb}成功：#{product.id} {product.name}')
            return redirect('workbench_detail', product_id=product.id)
        except (TypeError, ValueError):
            error = 'listing_id / dev_project_id 须为整数'
        except (XuanpinAPIError, XuanpinConfigError) as exc:
            error = str(exc)
        except Exception as exc:
            error = f'导入失败：{exc}'

    status = (request.GET.get('status') or '').strip()
    q = (request.GET.get('q') or '').strip()
    ml_site = (request.GET.get('ml_site') or cfg.default_ml_site or 'MLB').strip()

    xuanpin_items, xuanpin_count, xuanpin_list_error = [], 0, ''
    try:
        xuanpin_items, xuanpin_count = _fetch_xuanpin_listings(
            status=status, q=q, ml_site=ml_site,
        )
    except (XuanpinAPIError, XuanpinConfigError) as exc:
        xuanpin_list_error = str(exc)
    except Exception as exc:
        logger.exception('list xuanpin failed')
        xuanpin_list_error = f'拉取选品列表失败：{exc}'

    imported = {
        p.xuanpin_listing_id: p
        for p in ProductMaster.objects.exclude(xuanpin_listing_id=None)
    }
    for item in xuanpin_items:
        lid = item.get('listing_id')
        local = imported.get(lid)
        item['local_product_id'] = local.id if local else None
        item['already_imported'] = local is not None

    return render(request, 'workbench/home.html', {
        **_cfg_context(),
        'nav_active': 'import',
        'products': list(ProductMaster.objects.all().order_by('-updated_at')[:20]),
        'error': error,
        'xuanpin_items': xuanpin_items,
        'xuanpin_count': xuanpin_count,
        'xuanpin_list_error': xuanpin_list_error,
        'filters': {'status': status, 'q': q, 'ml_site': ml_site},
        'form': {
            'listing_id': request.POST.get('listing_id', ''),
            'dev_project_id': request.POST.get('dev_project_id', ''),
            'ml_site': ml_site,
        },
    })


@login_required
@require_http_methods(['GET', 'POST'])
def workbench_detail(request, product_id: int):
    product = get_object_or_404(
        ProductMaster.objects.prefetch_related('platform_listings'),
        pk=product_id,
    )
    tab = (request.GET.get('tab') or request.POST.get('tab') or 'context').strip()
    if tab not in VALID_TABS:
        tab = 'context'

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        try:
            if action == 'refresh':
                ml_site = (request.POST.get('ml_site') or '').strip() or None
                refresh_xuanpin_context(product, ml_site=ml_site)
                messages.success(request, '已从选品刷新上下文')
                return redirect(f"{request.path}?tab=context")

            if action == 'generate':
                count = int(request.POST.get('count') or 2)
                direction = (request.POST.get('direction') or '').strip()
                prompt = (request.POST.get('prompt') or '').strip()
                task, versions = create_candidates_from_context(
                    product, count=count, direction=direction, prompt=prompt,
                )
                messages.success(
                    request,
                    f'已生成 {len(versions)} 个候选（任务 #{task.id}）。请到「素材库」审核。',
                )
                return redirect(f"{request.path}?tab=assets")

            if action == 'upload_version':
                files = request.FILES.getlist('images')
                direction = (request.POST.get('direction') or '').strip()
                prompt = (request.POST.get('prompt') or '').strip()
                version = create_version_from_uploads(
                    product, files, prompt=prompt, direction=direction,
                )
                messages.success(request, f'已上传候选版本 {version.version_code}')
                return redirect(f"{request.path}?tab=assets")

            if action == 'review':
                version_id = int(request.POST.get('version_id'))
                review_action = (request.POST.get('review_action') or '').strip()
                version = get_object_or_404(CreativeVersion, pk=version_id, product=product)
                review_version(version, review_action)
                label = {'approve': '已通过', 'reject': '已驳回', 'pending': '改回待审'}.get(
                    review_action, review_action,
                )
                messages.success(request, f'{version.version_code} {label}')
                return redirect(f"{request.path}?tab=assets")

            if action == 'link_platform':
                item_id = (request.POST.get('item_id') or '').strip()
                ml_site = (request.POST.get('ml_site') or 'MLB').strip() or 'MLB'
                pl = ensure_platform_listing(product, item_id=item_id, ml_site=ml_site)
                messages.success(request, f'已绑定平台链接 {pl.ml_site}:{pl.item_id}')
                return redirect(f"{request.path}?tab=publish")

            if action == 'publish':
                version_id = int(request.POST.get('version_id'))
                listing_id = int(request.POST.get('platform_listing_id'))
                dry_run = (request.POST.get('dry_run') or '') in ('1', 'on', 'true')
                strategy = (request.POST.get('strategy') or 'replace_all').strip()
                version = get_object_or_404(CreativeVersion, pk=version_id, product=product)
                listing = get_object_or_404(
                    product.platform_listings, pk=listing_id,
                )
                history = publish_version_images(
                    platform_listing=listing,
                    version=version,
                    operator=request.user,
                    dry_run=dry_run,
                    strategy=strategy,
                )
                mode = '模拟' if dry_run or (history.snapshot_after_json or {}).get('dry_run') else '真实'
                messages.success(
                    request,
                    f'{mode}发布成功：历史 #{history.id}（{history.status}）',
                )
                return redirect(f"{request.path}?tab=history")

            if action == 'rollback':
                history_id = int(request.POST.get('history_id'))
                dry_run = (request.POST.get('dry_run') or '') in ('1', 'on', 'true')
                history = get_object_or_404(
                    PublicationHistory.objects.select_related('platform_listing'),
                    pk=history_id,
                    platform_listing__product=product,
                )
                rb = rollback_publication(
                    history=history, operator=request.user, dry_run=dry_run,
                )
                messages.success(request, f'已回滚：新记录 #{rb.id}')
                return redirect(f"{request.path}?tab=history")

            messages.warning(request, f'未知操作：{action}')
        except (TypeError, ValueError) as exc:
            messages.error(request, str(exc) or '参数错误')
        except (XuanpinAPIError, XuanpinConfigError, PlatformConfigError, PlatformError, PublishError) as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            logger.exception('workbench detail action failed')
            messages.error(request, str(exc))
        return redirect(f"{request.path}?tab={tab}")

    payload = serialize_product(product)
    versions = list_versions(product)
    approved_versions = [v for v in versions if v['review_status'] in ('approved', 'published')]
    publications = list_publications(product)
    platform_listings = list(product.platform_listings.all())
    meli_creds = resolve_meli_credentials(
        preferred_site=(platform_listings[0].ml_site if platform_listings else None),
    )
    preflight = None
    if tab == 'publish' and approved_versions and platform_listings:
        try:
            version_obj = CreativeVersion.objects.get(pk=approved_versions[0]['id'])
            preflight = preflight_publish(
                platform_listing=platform_listings[0],
                version=version_obj,
                dry_run=meli_dry_run_enabled() or not bool(meli_creds),
            )
        except Exception as exc:
            preflight = {'ok': False, 'checks': [{'ok': False, 'name': 'preflight', 'detail': str(exc)}]}

    return render(request, 'workbench/detail.html', {
        **_cfg_context(),
        'nav_active': 'workbench',
        'product': product,
        'payload': payload,
        'ctx': payload.get('xuanpin_context') or {},
        'tab': tab,
        'versions': versions,
        'approved_versions': approved_versions,
        'pending_count': sum(1 for v in versions if v['review_status'] == 'pending_review'),
        'approved_count': sum(1 for v in versions if v['review_status'] == 'approved'),
        'platform_listings': platform_listings,
        'publications': publications,
        'meli_token_ready': bool(meli_creds),
        'meli_dry_run_env': meli_dry_run_enabled(),
        'preflight': preflight,
    })


@login_required
@require_http_methods(['GET'])
def settings_xuanpin(request):
    return render(request, 'settings/xuanpin.html', {
        **_cfg_context(),
        'nav_active': 'xuanpin',
    })


@login_required
@require_http_methods(['GET'])
def settings_platforms(request):
    creds = resolve_meli_credentials()
    caps = {}
    try:
        adapter = get_meli_adapter(
            force_dry_run=meli_dry_run_enabled() or not bool(creds),
        )
        caps = adapter.capabilities()
    except Exception as exc:
        caps = {'error': str(exc)}
    return render(request, 'settings/platforms.html', {
        **_cfg_context(),
        'nav_active': 'platforms',
        'meli_token_ready': bool(creds),
        'meli_source': creds.source if creds else 'none',
        'meli_site': creds.site_id if creds else '',
        'meli_dry_run_env': meli_dry_run_enabled(),
        'meli_capabilities': caps,
    })
