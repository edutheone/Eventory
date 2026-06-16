from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from payments.screenshot_storage import (
    decode_data_uri,
    encode_upload_to_data_uri,
    open_screenshot_stream,
)


class ScreenshotStorageTests(TestCase):
    def test_round_trip_data_uri(self):
        upload = SimpleUploadedFile('pay.jpg', b'\xff\xd8\xfftest', content_type='image/jpeg')
        data_uri, raw = encode_upload_to_data_uri(upload)
        self.assertTrue(data_uri.startswith('data:image/jpeg;base64,'))
        self.assertEqual(raw, b'\xff\xd8\xfftest')
        decoded, mime = decode_data_uri(data_uri)
        self.assertEqual(decoded, raw)
        self.assertEqual(mime, 'image/jpeg')

    def test_open_screenshot_stream_from_order_like_object(self):
        upload = SimpleUploadedFile('pay.png', b'pngbytes', content_type='image/png')
        data_uri, _ = encode_upload_to_data_uri(upload)

        class Order:
            screenshot_data = data_uri
            screenshot = None

        stream = open_screenshot_stream(Order())
        self.assertIsNotNone(stream)
        self.assertEqual(stream.read(), b'pngbytes')
