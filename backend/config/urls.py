# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import include, path


def health(_request):
    return JsonResponse({
        'ok': True,
        'service': 'ai-listing-optimization',
        'docs': 'see ../docs/PRD-MVP.md',
    })


def home(_request):
    return redirect('products_list')


urlpatterns = [
    path('', home, name='home'),
    path('', include('apps.workbench.urls_ui')),
    path('accounts/logout/', LogoutView.as_view(next_page='/admin/login/'), name='logout'),
    path('admin/', admin.site.urls),
    path('api/health/', health, name='health'),
    path('api/', include('apps.workbench.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
