# -*- coding: utf-8 -*-
from __future__ import annotations

from apps.platforms.adapters.mercadolibre import MercadoLibreAdapter
from apps.platforms.exceptions import PlatformConfigError
from apps.platforms.services.credentials import meli_dry_run_enabled, resolve_meli_credentials


def get_meli_adapter(
    *,
    preferred_site: str | None = None,
    account=None,
    force_dry_run: bool | None = None,
) -> MercadoLibreAdapter:
    env_dry = meli_dry_run_enabled()
    dry = env_dry if force_dry_run is None else bool(force_dry_run)
    creds = resolve_meli_credentials(account=account, preferred_site=preferred_site)

    if dry:
        return MercadoLibreAdapter(
            access_token=(creds.access_token if creds else ''),
            site_id=(creds.site_id if creds else (preferred_site or 'MLB')),
            dry_run=True,
        )

    if not creds:
        raise PlatformConfigError(
            '未配置美客多 Token：请在 .env 设置 MELI_ACCESS_TOKEN，'
            '或在 Admin「平台账号」填写 token_ref；本地联调可勾选「模拟发布」',
        )
    return MercadoLibreAdapter(
        access_token=creds.access_token,
        site_id=creds.site_id,
        dry_run=False,
    )
