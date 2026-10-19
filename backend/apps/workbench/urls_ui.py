# -*- coding: utf-8 -*-
from django.urls import path

from . import ui_views

urlpatterns = [
    path('products/', ui_views.products_list, name='products_list'),
    path('workbench/', ui_views.workbench_home, name='workbench_home'),
    path('workbench/<int:product_id>/', ui_views.workbench_detail, name='workbench_detail'),
    path('settings/xuanpin/', ui_views.settings_xuanpin, name='settings_xuanpin'),
    path('settings/platforms/', ui_views.settings_platforms, name='settings_platforms'),
]
