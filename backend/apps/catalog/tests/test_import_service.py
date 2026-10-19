# -*- coding: utf-8 -*-
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from apps.catalog.models import PlatformListing, ProductMaster
from apps.catalog.services import import_from_xuanpin, refresh_xuanpin_context, serialize_product
from apps.catalog.services.fixtures import SAMPLE_LISTING_ID
from apps.catalog.services.xuanpin_http_client import XuanpinListingClient
from apps.catalog.services.xuanpin_mcp_client import XuanpinMCPClient


@override_settings(
    XUANPIN_USE_FIXTURES='0',
    XUANPIN_HTTP_BASE_URL='http://env-fallback.example',
    XUANPIN_MCP_BASE_URL='http://env-fallback.example/mcp/',
    XUANPIN_MCP_API_KEY='mcp_env_key',
)
class XuanpinAdminSettingsTests(TestCase):
    def test_admin_settings_override_env(self):
        from apps.catalog.models import XuanpinConnectionSettings
        from apps.catalog.services.settings_resolve import resolve_xuanpin_settings

        XuanpinConnectionSettings.objects.create(
            label='local',
            http_base_url='http://127.0.0.1:8000',
            mcp_base_url='http://127.0.0.1:8000/mcp/',
            api_key='mcp_admin_secret_key',
            default_ml_site='MLB',
            use_fixtures=True,
            is_active=True,
        )
        cfg = resolve_xuanpin_settings()
        self.assertEqual(cfg.source, 'admin')
        self.assertEqual(cfg.http_base_url, 'http://127.0.0.1:8000')
        self.assertEqual(cfg.api_key, 'mcp_admin_secret_key')
        self.assertTrue(cfg.use_fixtures)

    def test_env_fallback_when_no_admin_row(self):
        from apps.catalog.services.settings_resolve import resolve_xuanpin_settings

        cfg = resolve_xuanpin_settings()
        self.assertEqual(cfg.source, 'env')
        self.assertEqual(cfg.api_key, 'mcp_env_key')


@override_settings(XUANPIN_USE_FIXTURES='1')
class ImportFromXuanpinTests(TestCase):
    def setUp(self):
        self.listing_client = XuanpinListingClient(use_fixtures=True)
        self.mcp_client = XuanpinMCPClient(use_fixtures=True)

    def test_import_creates_product_and_platform_listing(self):
        result = import_from_xuanpin(
            listing_id=SAMPLE_LISTING_ID,
            ml_site='MLB',
            listing_client=self.listing_client,
            mcp_client=self.mcp_client,
        )
        self.assertTrue(result['created'])
        product = result['product']
        self.assertEqual(product.xuanpin_listing_id, SAMPLE_LISTING_ID)
        self.assertTrue(product.name)
        self.assertTrue(product.cover_image_url)
        self.assertEqual(product.xuanpin_dev_project_id, 45)
        ctx = product.xuanpin_context_json
        self.assertEqual(ctx['listing_id'], SAMPLE_LISTING_ID)
        self.assertTrue(ctx['image_urls'])
        self.assertTrue(ctx['brief'].get('report_excerpt') or ctx['brief'].get('task_id'))

        pl = result['platform_listing']
        self.assertIsNotNone(pl)
        self.assertEqual(pl.platform, PlatformListing.PLATFORM_ML)
        self.assertEqual(pl.item_id, 'MLB1234567890')

        payload = serialize_product(product)
        self.assertEqual(payload['id'], product.id)
        self.assertIn('xuanpin_context', payload)

    def test_import_is_idempotent_by_listing_id(self):
        import_from_xuanpin(
            listing_id=SAMPLE_LISTING_ID,
            listing_client=self.listing_client,
            mcp_client=self.mcp_client,
        )
        result = import_from_xuanpin(
            listing_id=SAMPLE_LISTING_ID,
            listing_client=self.listing_client,
            mcp_client=self.mcp_client,
        )
        self.assertFalse(result['created'])
        self.assertEqual(ProductMaster.objects.filter(xuanpin_listing_id=SAMPLE_LISTING_ID).count(), 1)

    def test_import_by_dev_project_id(self):
        result = import_from_xuanpin(
            dev_project_id=45,
            listing_client=self.listing_client,
            mcp_client=self.mcp_client,
        )
        self.assertEqual(result['product'].xuanpin_listing_id, SAMPLE_LISTING_ID)

    def test_refresh_updates_context_only(self):
        result = import_from_xuanpin(
            listing_id=SAMPLE_LISTING_ID,
            listing_client=self.listing_client,
            mcp_client=self.mcp_client,
        )
        product = result['product']
        product.xuanpin_context_json = {'stale': True}
        product.save(update_fields=['xuanpin_context_json'])

        refreshed = refresh_xuanpin_context(
            product,
            listing_client=self.listing_client,
            mcp_client=self.mcp_client,
        )
        ctx = refreshed['product'].xuanpin_context_json
        self.assertNotIn('stale', ctx)
        self.assertEqual(ctx['listing_id'], SAMPLE_LISTING_ID)


@override_settings(XUANPIN_USE_FIXTURES='1')
class WorkbenchImportAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='ops', password='pass12345')
        self.client = Client()
        self.client.force_login(self.user)

    def test_import_and_detail_and_refresh(self):
        resp = self.client.post(
            '/api/products/import-from-xuanpin/',
            data='{"listing_id": 90001, "ml_site": "MLB"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertTrue(body['created'])
        product_id = body['product']['id']
        self.assertEqual(body['product']['xuanpin_listing_id'], SAMPLE_LISTING_ID)
        self.assertTrue(body['product']['xuanpin_context']['image_urls'])

        detail = self.client.get(f'/api/products/{product_id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['product']['id'], product_id)

        refresh = self.client.post(
            f'/api/products/{product_id}/refresh-xuanpin/',
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(refresh.status_code, 200, refresh.content)
        self.assertTrue(refresh.json()['success'])

    def test_import_requires_auth(self):
        anon = Client()
        resp = anon.post(
            '/api/products/import-from-xuanpin/',
            data='{"listing_id": 90001}',
            content_type='application/json',
        )
        self.assertIn(resp.status_code, (302, 401, 403))

    def test_mvp_meta_shows_w1_ready(self):
        resp = self.client.get('/api/meta/mvp/')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['w1']['import_from_xuanpin'], 'ready')
        self.assertTrue(body['w1']['xuanpin_use_fixtures'])
