# -*- coding: utf-8 -*-
"""选品 MCP JSON-RPC 客户端：调研喂料（简报等），失败不阻断导入。"""
from __future__ import annotations

import json
import logging
import itertools
from typing import Any

import requests

from .exceptions import XuanpinAPIError, XuanpinConfigError
from . import fixtures
from .settings_resolve import resolve_xuanpin_settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 45
_rpc_id = itertools.count(1)


class XuanpinMCPClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        use_fixtures: bool | None = None,
        session: requests.Session | None = None,
    ):
        cfg = resolve_xuanpin_settings() if (
            base_url is None or api_key is None or use_fixtures is None
        ) else None
        if base_url is not None:
            raw = base_url
        else:
            raw = cfg.mcp_base_url if cfg else ''
        self.base_url = raw.rstrip('/') + '/' if raw else ''
        self.api_key = api_key if api_key is not None else (cfg.api_key if cfg else '')
        self.timeout = timeout
        if use_fixtures is None:
            use_fixtures = bool(cfg.use_fixtures) if cfg else False
        self.use_fixtures = use_fixtures
        self._session = session or requests.Session()

    def _ensure_config(self) -> None:
        if self.use_fixtures:
            return
        if not self.base_url or self.base_url == '/':
            raise XuanpinConfigError(
                '未配置选品 MCP Base：请在 Admin「选品连接配置」填写，或设 XUANPIN_MCP_BASE_URL',
            )
        if not self.api_key:
            raise XuanpinConfigError(
                '未配置 MCP API Key：请在 Admin「选品连接配置」填写，或设 XUANPIN_MCP_API_KEY',
            )

    def call_tool(
        self,
        name: str,
        arguments: dict | None = None,
        *,
        ml_site: str | None = None,
    ) -> dict[str, Any]:
        if self.use_fixtures:
            return self._fixture_tool(name, arguments or {})

        self._ensure_config()
        payload = {
            'jsonrpc': '2.0',
            'id': next(_rpc_id),
            'method': 'tools/call',
            'params': {
                'name': name,
                'arguments': arguments or {},
            },
        }
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if ml_site:
            headers['X-ML-Site'] = ml_site

        try:
            resp = self._session.post(
                self.base_url, json=payload, headers=headers, timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise XuanpinAPIError(f'MCP 网络错误: {exc}', status_code=502, code='network') from exc

        if resp.status_code == 401:
            raise XuanpinAPIError('MCP API Key 无效', status_code=401, code='unauthorized')
        if resp.status_code >= 400:
            raise XuanpinAPIError(
                f'MCP HTTP {resp.status_code}: {(resp.text or "")[:200]}',
                status_code=502,
                code='upstream_http',
            )

        try:
            body = resp.json()
        except ValueError as exc:
            raise XuanpinAPIError('MCP 返回非 JSON', status_code=502, code='bad_json') from exc

        if 'error' in body and body['error']:
            err = body['error']
            msg = err.get('message') if isinstance(err, dict) else str(err)
            raise XuanpinAPIError(f'MCP RPC 错误: {msg}', status_code=502, code='rpc_error')

        result = body.get('result') or {}
        if result.get('isError'):
            text = ''
            for block in result.get('content') or []:
                if isinstance(block, dict) and block.get('type') == 'text':
                    text = block.get('text') or ''
                    break
            raise XuanpinAPIError(text or 'MCP tool isError', status_code=502, code='tool_error')

        structured = result.get('structuredContent')
        if isinstance(structured, dict):
            return structured

        # 回退：解析 content[0].text JSON
        for block in result.get('content') or []:
            if not isinstance(block, dict) or block.get('type') != 'text':
                continue
            text = block.get('text') or ''
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {'success': True, 'text': text}
        return {'success': True, 'raw': result}

    def get_stakeholder_brief(
        self,
        task_id: int,
        *,
        ml_site: str | None = None,
        include_raw_skus: bool = False,
        include_packs: bool = True,
    ) -> dict[str, Any]:
        return self.call_tool(
            'get_stakeholder_brief',
            {
                'task_id': int(task_id),
                'include_raw_skus': include_raw_skus,
                'include_packs': include_packs,
            },
            ml_site=ml_site,
        )

    def _fixture_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        if name == 'get_stakeholder_brief':
            return {
                'success': True,
                'brief': {
                    **fixtures.SAMPLE_BRIEF_SUMMARY,
                    'task_id': int(arguments.get('task_id') or fixtures.SAMPLE_BRIEF_SUMMARY['task_id']),
                    'listing_pack': {'title': 'Fixture pack'},
                    'image_brief_pack': {'hero': '实拍主图约束'},
                    'report_text': fixtures.SAMPLE_BRIEF_SUMMARY['report_excerpt'],
                },
            }
        return {'success': False, 'error': f'fixture 未实现工具: {name}'}


def summarize_brief_for_cache(brief_payload: dict | None) -> dict[str, Any]:
    """压缩简报进 xuanpin_context_json，避免整包过大。"""
    if not brief_payload:
        return {}
    brief = brief_payload.get('brief') if isinstance(brief_payload.get('brief'), dict) else brief_payload
    if not isinstance(brief, dict):
        return {}

    listing_pack = brief.get('listing_pack') or {}
    image_pack = brief.get('image_brief_pack') or {}
    report = brief.get('report_text') or brief.get('report_excerpt') or ''
    if isinstance(report, str) and len(report) > 800:
        report = report[:800] + '…'

    return {
        'task_id': brief.get('task_id') or brief.get('id'),
        'title': brief.get('title') or brief.get('name') or '',
        'report_excerpt': report,
        'listing_pack_keys': sorted(listing_pack.keys()) if isinstance(listing_pack, dict) else [],
        'image_brief_pack_keys': sorted(image_pack.keys()) if isinstance(image_pack, dict) else [],
        'listing_pack_summary': _shallow_pack(listing_pack),
        'image_brief_pack_summary': _shallow_pack(image_pack),
    }


def _shallow_pack(pack: Any) -> dict:
    if not isinstance(pack, dict):
        return {}
    out = {}
    for k, v in list(pack.items())[:20]:
        if isinstance(v, str):
            out[k] = v[:300] + ('…' if len(v) > 300 else '')
        elif isinstance(v, (int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, list):
            out[k] = v[:5]
        else:
            out[k] = str(type(v).__name__)
    return out


def get_default_mcp_client() -> XuanpinMCPClient:
    cfg = resolve_xuanpin_settings()
    return XuanpinMCPClient(
        base_url=cfg.mcp_base_url,
        api_key=cfg.api_key,
        use_fixtures=cfg.use_fixtures,
    )
