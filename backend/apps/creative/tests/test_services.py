# -*- coding: utf-8 -*-
from django.test import TestCase

from apps.catalog.models import ProductMaster
from apps.creative.models import CreativeVersion
from apps.creative.services import create_candidates_from_context, review_version


class CreativeServicesTests(TestCase):
    def setUp(self):
        self.product = ProductMaster.objects.create(
            name='测试商品',
            cover_image_url='https://example.com/a.jpg',
            xuanpin_context_json={
                'image_urls': [
                    'https://example.com/a.jpg',
                    'https://example.com/b.jpg',
                ],
            },
        )

    def test_generate_and_review(self):
        task, versions = create_candidates_from_context(self.product, count=2, direction='场景')
        self.assertEqual(task.status, 'succeeded')
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].review_status, CreativeVersion.REVIEW_PENDING)

        reviewed = review_version(versions[0], 'approve')
        self.assertEqual(reviewed.review_status, CreativeVersion.REVIEW_APPROVED)

        rejected = review_version(versions[1], 'reject')
        self.assertEqual(rejected.review_status, CreativeVersion.REVIEW_REJECTED)
