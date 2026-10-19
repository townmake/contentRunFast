# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalog.models import PlatformListing, ProductMaster
from apps.creative.models import CreativeVersion
from apps.creative.services import create_candidates_from_context, review_version
from apps.publish.models import PublicationHistory
from apps.publish.services import publish_version_images, rollback_publication


class PublishDryRunTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('ops', password='x')
        self.product = ProductMaster.objects.create(
            name='发布测试',
            cover_image_url='https://httpbin.org/image/jpeg',
            xuanpin_context_json={
                'image_urls': [
                    'https://httpbin.org/image/jpeg',
                    'https://httpbin.org/image/png',
                ],
            },
        )
        self.listing = PlatformListing.objects.create(
            product=self.product,
            platform=PlatformListing.PLATFORM_ML,
            ml_site='MLB',
            item_id='MLB999000111',
            sync_status='linked',
        )
        _task, versions = create_candidates_from_context(self.product, count=1)
        self.version = review_version(versions[0], 'approve')

    def test_publish_and_rollback_dry_run(self):
        history = publish_version_images(
            platform_listing=self.listing,
            version=self.version,
            operator=self.user,
            dry_run=True,
            strategy='replace_all',
        )
        self.assertEqual(history.status, PublicationHistory.STATUS_SUCCEEDED)
        self.assertTrue(history.snapshot_before_json.get('pictures'))
        self.assertTrue(history.snapshot_after_json.get('pictures'))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.current_version_id, self.version.id)

        rb = rollback_publication(history=history, operator=self.user, dry_run=True)
        self.assertEqual(rb.status, PublicationHistory.STATUS_ROLLED_BACK)
        history.refresh_from_db()
        self.assertEqual(history.status, PublicationHistory.STATUS_ROLLED_BACK)
