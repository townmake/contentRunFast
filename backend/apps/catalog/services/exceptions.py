# -*- coding: utf-8 -*-
from __future__ import annotations


class XuanpinConfigError(Exception):
    """本系统未配置选品 Base URL / API Key。"""


class XuanpinAPIError(Exception):
    """选品 HTTP / MCP 调用失败。"""

    def __init__(self, message: str, *, status_code: int = 502, code: str = 'xuanpin_error'):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code

    def to_dict(self) -> dict:
        return {
            'success': False,
            'error': self.message,
            'code': self.code,
        }
