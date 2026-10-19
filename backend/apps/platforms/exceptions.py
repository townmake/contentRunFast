# -*- coding: utf-8 -*-
from __future__ import annotations


class PlatformError(Exception):
    def __init__(self, message: str, *, code: str = 'platform_error', status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class PlatformConfigError(PlatformError):
    def __init__(self, message: str):
        super().__init__(message, code='config', status_code=503)
