# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from dataclasses import dataclass

from django.conf import settings

from apps.platforms.models import PlatformAccount


@dataclass(frozen=True)
class MeliCredentials:
    access_token: str
    site_id: str
    account: PlatformAccount | None = None
    source: str = 'env'  # env | account | dry_run


def resolve_meli_credentials(
    *,
    account: PlatformAccount | None = None,
    preferred_site: str | None = None,
) -> MeliCredentials | None:
    site = (preferred_site or '').strip().upper()
    if account is None:
        account = (
            PlatformAccount.objects
            .filter(platform='mercadolibre', is_active=True)
            .order_by('-updated_at')
            .first()
        )
        if site:
            account = (
                PlatformAccount.objects
                .filter(platform='mercadolibre', is_active=True, ml_site__iexact=site)
                .order_by('-updated_at')
                .first()
            ) or account

    token = ''
    source = 'env'
    if account and (account.token_ref or '').strip():
        ref = account.token_ref.strip()
        if ref.startswith('env:'):
            token = (os.getenv(ref[4:].strip(), '') or getattr(settings, ref[4:].strip(), '') or '').strip()
            source = 'account_env'
        elif ref.isupper() and ' ' not in ref and len(ref) < 64:
            token = (getattr(settings, ref, '') or os.getenv(ref, '') or '').strip()
            source = 'account_env'
        else:
            token = ref
            source = 'account'

    if not token:
        token = (getattr(settings, 'MELI_ACCESS_TOKEN', '') or '').strip()
        source = 'env'

    if not token:
        return None

    site_id = site or (account.ml_site if account else '') or getattr(settings, 'MELI_SITE_ID', 'MLB') or 'MLB'
    return MeliCredentials(
        access_token=token,
        site_id=str(site_id).upper(),
        account=account,
        source=source,
    )


def meli_dry_run_enabled() -> bool:
    return str(getattr(settings, 'MELI_DRY_RUN', '') or '').lower() in ('1', 'true', 'yes', 'on')
