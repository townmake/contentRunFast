# -*- coding: utf-8 -*-
from django.urls import path

from . import views

urlpatterns = [
    path('meta/mvp/', views.mvp_meta, name='api_mvp_meta'),
    path('products/', views.product_list, name='api_products'),
    path('products/import-from-xuanpin/', views.import_from_xuanpin_view, name='api_import_xuanpin'),
    path('products/<int:product_id>/', views.product_detail, name='api_product_detail'),
    path(
        'products/<int:product_id>/refresh-xuanpin/',
        views.refresh_xuanpin_view,
        name='api_refresh_xuanpin',
    ),
]
