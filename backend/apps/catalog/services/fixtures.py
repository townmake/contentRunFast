# -*- coding: utf-8 -*-
"""本地联调假数据：选品 Listing 只读 API 未就绪时，设 XUANPIN_USE_FIXTURES=1。"""
from __future__ import annotations

SAMPLE_LISTING_ID = 90001

SAMPLE_LISTING = {
    'listing_id': SAMPLE_LISTING_ID,
    'title': 'Fixture 无钢圈舒适文胸',
    'listing_title': 'Sutiã Sem Aro Conforto — Fixture',
    'status': 'pending',
    'source_type': 'dev_project',
    'dev_project_id': 45,
    'platform_product_id': 678,
    'platform_sku': 'MLB1234567890',
    'stakeholder_brief_id': 9,
    'ml_listing_summary_id': 3,
    'listing_bullets': [
        'Sem aro, suporte diário',
        'Tecido respirável',
        'Costura plana anti-irritação',
    ],
    'listing_characteristics': {'material': 'algodão'},
    'listing_description': 'Fixture listing description for import smoke test.',
    'listing_image_urls': [
        'https://httpbin.org/image/jpeg',
        'https://httpbin.org/image/png',
    ],
    'gallery_urls': [
        'https://httpbin.org/image/jpeg',
    ],
    'remark': 'fixture',
    'created_by': 'fixture',
    'updated_at': '2026-10-18T10:00:00+08:00',
}

SAMPLE_CONTENT_PRODUCTION = {
    'listing_id': SAMPLE_LISTING_ID,
    'status': 'draft',
    'mlb_payload': {'title': SAMPLE_LISTING['listing_title']},
    'shopee_payload': {},
    'updated_at': '2026-10-18T10:00:00+08:00',
}

SAMPLE_IMAGES = {
    'listing_id': SAMPLE_LISTING_ID,
    'images': [
        {'index': 0, 'url': 'https://httpbin.org/image/jpeg', 'source': 'url'},
        {'index': 1, 'url': 'https://httpbin.org/image/png', 'source': 'upload'},
    ],
}

SAMPLE_FAQS = [
    {
        'id': 1,
        'question_pt': 'Tem aro?',
        'answer_pt': 'Não, é sem aro.',
        'question_zh': '有钢圈吗？',
        'answer_zh': '没有，无钢圈。',
    },
]

SAMPLE_BRIEF_SUMMARY = {
    'task_id': 9,
    'title': 'Fixture 简报',
    'listing_pack_keys': ['title', 'bullets', 'description'],
    'image_brief_pack_keys': ['hero', 'detail', 'size_chart'],
    'report_excerpt': '卖点：舒适无钢圈；痛点：钢圈勒；作图：实拍+场景。',
}


def fixture_list_listings(*, q: str | None = None, **_kwargs) -> dict:
    item = {
        'listing_id': SAMPLE_LISTING['listing_id'],
        'title': SAMPLE_LISTING['title'],
        'listing_title': SAMPLE_LISTING['listing_title'],
        'status': SAMPLE_LISTING['status'],
        'dev_project_id': SAMPLE_LISTING['dev_project_id'],
        'platform_product_id': SAMPLE_LISTING['platform_product_id'],
        'platform_sku': SAMPLE_LISTING['platform_sku'],
        'stakeholder_brief_id': SAMPLE_LISTING['stakeholder_brief_id'],
        'primary_image_url': SAMPLE_LISTING['listing_image_urls'][0],
        'updated_at': SAMPLE_LISTING['updated_at'],
    }
    items = [item]
    if q and q.lower() not in (item['title'] + item['listing_title']).lower():
        items = []
    return {'success': True, 'count': len(items), 'items': items}
