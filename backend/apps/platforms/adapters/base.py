# -*- coding: utf-8 -*-
"""平台适配器基类。能力值：supported | needs_permission | unavailable"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PlatformAdapter(ABC):
    platform: str = ''

    @abstractmethod
    def capabilities(self) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def get_product(self, item_ref: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def upload_asset(self, file_bytes: bytes, *, filename: str = 'image.jpg') -> str:
        raise NotImplementedError

    @abstractmethod
    def update_listing_images(self, item_ref: str, image_ids_ordered: list[str]) -> dict[str, Any]:
        """必须先 get_product 保留完整图片数组，再整表写回。"""
        raise NotImplementedError
