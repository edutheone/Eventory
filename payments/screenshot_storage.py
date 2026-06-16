"""In-memory / database-backed payment screenshots for serverless (read-only FS)."""

from __future__ import annotations

import base64
import binascii
import re
from io import BytesIO

DATA_URI_RE = re.compile(r'^data:(?P<content_type>[^;]+);base64,(?P<data>.+)$', re.DOTALL)


def encode_upload_to_data_uri(uploaded_file, *, content_type: str | None = None) -> tuple[str, bytes]:
    """Return (data URI, raw bytes) from an uploaded file."""
    raw = uploaded_file.read()
    mime = content_type or getattr(uploaded_file, 'content_type', '') or 'image/jpeg'
    if mime not in {'image/jpeg', 'image/png', 'image/webp'}:
        mime = 'image/jpeg'
    encoded = base64.b64encode(raw).decode('ascii')
    return f'data:{mime};base64,{encoded}', raw


def decode_data_uri(data_uri: str) -> tuple[bytes, str]:
    match = DATA_URI_RE.match((data_uri or '').strip())
    if not match:
        raise ValueError('Invalid screenshot data URI.')
    content_type = match.group('content_type')
    raw = base64.b64decode(match.group('data'))
    return raw, content_type


def open_screenshot_stream(order) -> BytesIO | None:
    """Open payment screenshot bytes for OCR or display."""
    if getattr(order, 'screenshot_data', None):
        try:
            raw, _ = decode_data_uri(order.screenshot_data)
            return BytesIO(raw)
        except (ValueError, binascii.Error):
            return None
    screenshot_field = getattr(order, 'screenshot', None)
    if screenshot_field:
        try:
            screenshot_field.open('rb')
            try:
                return BytesIO(screenshot_field.read())
            finally:
                screenshot_field.close()
        except OSError:
            return None
    return None


def order_has_screenshot(order) -> bool:
    return bool(getattr(order, 'screenshot_data', None) or getattr(order, 'screenshot', None))
