# -*- coding: utf-8 -*-
"""MVP settings — SQLite by default; override via env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / '.env')
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-only-insecure-key')
DEBUG = os.getenv('DJANGO_DEBUG', '1') in ('1', 'true', 'True', 'yes')
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
    if h.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'apps.catalog',
    'apps.creative',
    'apps.publish',
    'apps.platforms',
    'apps.workbench',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/products/'

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
}

CORS_ALLOW_ALL_ORIGINS = DEBUG

# 本地 Admin CSRF：避免 127.0.0.1 / localhost 混用或浏览器 Origin 校验导致 403
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        'DJANGO_CSRF_TRUSTED_ORIGINS',
        'http://127.0.0.1:8100,http://localhost:8100',
    ).split(',')
    if o.strip()
]
# 与选品系统（同主机 127.0.0.1:8000）隔离 Cookie，避免互相覆盖 sessionid/csrftoken
# 浏览器 Cookie 不区分端口，两套 Django 若同名会把对方登录态冲掉
SESSION_COOKIE_NAME = 'runfast_sessionid'
CSRF_COOKIE_NAME = 'runfast_csrftoken'
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 天
SESSION_SAVE_EVERY_REQUEST = True        # 有请求就续期（keepalive）
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# 选品 / 美客多 / AI（见 .env.example）

_mcp_base = (os.getenv('XUANPIN_MCP_BASE_URL', '') or '').strip()
XUANPIN_MCP_BASE_URL = (_mcp_base.rstrip('/') + '/') if _mcp_base else ''
XUANPIN_MCP_API_KEY = os.getenv('XUANPIN_MCP_API_KEY', '')
XUANPIN_HTTP_BASE_URL = (os.getenv('XUANPIN_HTTP_BASE_URL', '') or '').rstrip('/')
# 选品 Listing 只读未上线时：设为 1，用本地 fixture 走通导入/刷新
XUANPIN_USE_FIXTURES = os.getenv('XUANPIN_USE_FIXTURES', '0')
MELI_SITE_ID = os.getenv('MELI_SITE_ID', 'MLB')
MELI_ACCESS_TOKEN = os.getenv('MELI_ACCESS_TOKEN', '')
# 1=默认走模拟发布（不写真实美客多）；工作台也可单次勾选「模拟发布」
MELI_DRY_RUN = os.getenv('MELI_DRY_RUN', '0')
AI_IMAGE_PROVIDER = os.getenv('AI_IMAGE_PROVIDER', '')
AI_IMAGE_API_KEY = os.getenv('AI_IMAGE_API_KEY', '')
