# -*- coding: utf-8 -*-
"""W2：素材版本创建 / 审核 / 占位生成。"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import ProductMaster
from apps.creative.models import AIGenerationTask, CreativeAsset, CreativeVersion


def _new_version_code(product: ProductMaster) -> str:
    stamp = timezone.now().strftime('%Y%m%d%H%M%S')
    return f'v{product.id}-{stamp}-{uuid.uuid4().hex[:4]}'


def _save_upload(product: ProductMaster, uploaded: UploadedFile) -> CreativeAsset:
    media_root = Path(settings.MEDIA_ROOT)
    rel_dir = Path('creatives') / str(product.id)
    abs_dir = media_root / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(uploaded.name or 'image.jpg').suffix or '.jpg'
    filename = f'{uuid.uuid4().hex}{suffix.lower()}'
    abs_path = abs_dir / filename

    h = hashlib.sha256()
    with abs_path.open('wb') as out:
        for chunk in uploaded.chunks():
            out.write(chunk)
            h.update(chunk)

    uri = f'{settings.MEDIA_URL.rstrip("/")}/{rel_dir.as_posix()}/{filename}'
    return CreativeAsset.objects.create(
        product=product,
        asset_type=CreativeAsset.TYPE_IMAGE,
        uri=uri,
        sha256=h.hexdigest(),
        source='upload',
        meta_json={'filename': uploaded.name or filename},
    )


def _asset_from_url(product: ProductMaster, url: str, *, source: str = 'xuanpin') -> CreativeAsset:
    return CreativeAsset.objects.create(
        product=product,
        asset_type=CreativeAsset.TYPE_IMAGE,
        uri=url,
        source=source,
        meta_json={'from_url': True},
    )


@transaction.atomic
def create_version_from_uploads(
    product: ProductMaster,
    files: Iterable[UploadedFile],
    *,
    prompt: str = '',
    direction: str = '',
) -> CreativeVersion:
    uploads = [f for f in files if f]
    if not uploads:
        raise ValueError('请至少上传一张图片')

    assets = [_save_upload(product, f) for f in uploads]
    version = CreativeVersion.objects.create(
        product=product,
        version_code=_new_version_code(product),
        role=CreativeVersion.ROLE_CANDIDATE,
        review_status=CreativeVersion.REVIEW_PENDING,
        prompt=prompt or direction,
        model_name='manual-upload',
        payload={
            'direction': direction,
            'image_uris': [a.uri for a in assets],
            'source': 'upload',
        },
    )
    version.assets.set(assets)
    return version


@transaction.atomic
def create_candidates_from_context(
    product: ProductMaster,
    *,
    count: int = 2,
    direction: str = '',
    prompt: str = '',
) -> tuple[AIGenerationTask, list[CreativeVersion]]:
    """
    W2 过渡：尚无真实图像模型时，用选品上下文图生成候选版本，便于走通审核流。
    有 AI_IMAGE_API_KEY 时仍先走同一路径，并在 task.params 标记 provider。
    """
    count = max(1, min(int(count or 2), 5))
    ctx = product.xuanpin_context_json or {}
    urls = list(ctx.get('image_urls') or [])
    if product.cover_image_url and product.cover_image_url not in urls:
        urls.insert(0, product.cover_image_url)
    if not urls:
        raise ValueError('商品上下文没有可用图片，请先从选品刷新或手工上传')

    provider = (getattr(settings, 'AI_IMAGE_PROVIDER', '') or 'stub').strip() or 'stub'
    task = AIGenerationTask.objects.create(
        product=product,
        params_json={
            'count': count,
            'direction': direction,
            'prompt': prompt,
            'provider': provider,
            'mode': 'context_stub' if not getattr(settings, 'AI_IMAGE_API_KEY', '') else 'provider_pending',
        },
        status=AIGenerationTask.STATUS_RUNNING,
    )

    versions: list[CreativeVersion] = []
    try:
        for i in range(count):
            # 轮转取图，保证多候选略有差异
            pick = urls[i % len(urls):] + urls[: i % len(urls)]
            pick = pick[: min(3, len(urls))] or urls[:1]
            assets = [_asset_from_url(product, u, source='xuanpin') for u in pick]
            version = CreativeVersion.objects.create(
                product=product,
                version_code=_new_version_code(product) + f'-c{i+1}',
                role=CreativeVersion.ROLE_CANDIDATE,
                review_status=CreativeVersion.REVIEW_PENDING,
                prompt=prompt or direction or f'候选 {i+1}（基于选品实拍图）',
                model_name=provider or 'context-stub',
                payload={
                    'direction': direction,
                    'image_uris': [a.uri for a in assets],
                    'source': 'generate_stub',
                    'candidate_index': i + 1,
                },
            )
            version.assets.set(assets)
            versions.append(version)

        task.status = AIGenerationTask.STATUS_SUCCEEDED
        task.result_version_ids = [v.id for v in versions]
        task.save(update_fields=['status', 'result_version_ids', 'updated_at'])
    except Exception as exc:
        task.status = AIGenerationTask.STATUS_FAILED
        task.error = str(exc)[:1000]
        task.save(update_fields=['status', 'error', 'updated_at'])
        raise

    return task, versions


@transaction.atomic
def review_version(version: CreativeVersion, action: str) -> CreativeVersion:
    action = (action or '').strip().lower()
    if action == 'approve':
        version.review_status = CreativeVersion.REVIEW_APPROVED
        version.role = CreativeVersion.ROLE_CANDIDATE
    elif action == 'reject':
        version.review_status = CreativeVersion.REVIEW_REJECTED
        version.role = CreativeVersion.ROLE_ARCHIVED
    elif action == 'pending':
        version.review_status = CreativeVersion.REVIEW_PENDING
        version.role = CreativeVersion.ROLE_CANDIDATE
    else:
        raise ValueError('action 须为 approve / reject / pending')
    version.save(update_fields=['review_status', 'role', 'updated_at'])
    return version


def serialize_version(version: CreativeVersion) -> dict:
    assets = list(version.assets.all())
    uris = [a.uri for a in assets] or list((version.payload or {}).get('image_uris') or [])
    return {
        'id': version.id,
        'version_code': version.version_code,
        'role': version.role,
        'review_status': version.review_status,
        'prompt': version.prompt,
        'model_name': version.model_name,
        'image_uris': uris,
        'payload': version.payload or {},
        'created_at': version.created_at.isoformat() if version.created_at else None,
    }


def list_versions(product: ProductMaster) -> list[dict]:
    qs = (
        CreativeVersion.objects
        .filter(product=product)
        .prefetch_related('assets')
        .order_by('-created_at')
    )
    return [serialize_version(v) for v in qs]
