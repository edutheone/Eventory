import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta

from events.models import Event, Category
from bookings.models import Ticket
from payments.models import PaymentOrder, OrganizerNotification, AttendeeNotification
from bookings.services import compute_tier_price, compute_order_total, fulfill_payment_order, FulfillmentError
from payments.screenshot_verifier import verify_screenshot, _amount_matches, _fuzzy_name_match

User = get_user_model()


class MpesaSettingsTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username='org1', email='org@test.com', password='pass12345', role='organizer'
        )
        self.client = Client()

    def test_organizer_mpesa_config_validation(self):
        self.organizer.mpesa_display_name = 'EventHub Digital'
        self.organizer.mpesa_till = '123456'
        self.assertTrue(self.organizer.has_mpesa_payment_config())
        self.assertEqual(len(self.organizer.mpesa_payment_options()), 1)


class PaymentOrderTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username='org2', email='org2@test.com', password='pass12345', role='organizer',
            mpesa_display_name='EventHub Digital', mpesa_till='999888',
        )
        self.attendee = User.objects.create_user(
            username='att1', email='att@test.com', password='pass12345', role='attendee'
        )
        self.category = Category.objects.create(name='Music', slug='music')
        self.event = Event.objects.create(
            title='Test Concert',
            slug='test-concert',
            description='Test',
            category=self.category,
            organizer=self.organizer,
            start_date=timezone.now() + timedelta(days=7),
            end_date=timezone.now() + timedelta(days=7, hours=3),
            venue='Nairobi',
            price=Decimal('1000'),
            vip_price=Decimal('2500'),
            total_seats=100,
            available_seats=100,
            status='published',
        )

    def test_compute_tier_price_vip(self):
        self.assertEqual(compute_tier_price(self.event, 'VIP'), Decimal('2500'))
        self.assertEqual(compute_tier_price(self.event, 'Regular'), Decimal('1000'))

    def test_create_payment_order_api(self):
        self.client.force_login(self.attendee)
        response = self.client.post(
            '/api/attendee/payment-orders/create/',
            data='{"event_id": %d, "ticket_type": "VIP", "quantity": 2}' % self.event.id,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['order']['total_amount'], 5000.0)
        self.assertEqual(data['order']['ticket_type'], 'VIP')

    def test_fulfill_payment_order_decrements_seats(self):
        order = PaymentOrder.objects.create(
            attendee=self.attendee,
            event=self.event,
            organizer=self.organizer,
            ticket_type='Regular',
            quantity=3,
            unit_price=Decimal('1000'),
            total_amount=Decimal('3000'),
            status='pending_payment',
        )
        ticket = fulfill_payment_order(order)
        self.event.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.event.available_seats, 97)
        self.assertEqual(order.status, 'completed')
        self.assertEqual(ticket.ticket_type, 'Regular')
        self.assertEqual(ticket.quantity, 3)

    def test_approve_manual_review_order(self):
        order = PaymentOrder.objects.create(
            attendee=self.attendee,
            event=self.event,
            organizer=self.organizer,
            ticket_type='VIP',
            quantity=1,
            unit_price=Decimal('2500'),
            total_amount=Decimal('2500'),
            status='manual_review',
            submitted_mpesa_name='JOHN DOE',
        )
        seats_before = self.event.available_seats
        self.client.force_login(self.organizer)
        response = self.client.post(f'/api/organizer/payment-orders/{order.id}/approve/')
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['ticket_number'])
        order.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual(order.status, 'completed')
        self.assertEqual(self.event.available_seats, seats_before - 1)
        ticket = Ticket.objects.get(attendee=self.attendee, ticket_type='VIP')
        self.assertEqual(ticket.ticket_number, data['ticket_number'])
        self.assertEqual(ticket.quantity, 1)

    @patch('payments.order_views.analyze_payment_screenshot')
    def test_verify_screenshot_routes_to_organizer_on_ocr_pass(self, mock_analyze):
        mock_analyze.return_value = {
            'success': True,
            'ocr_text': 'KES 2500 paid to EventHub Digital',
            'notes': 'Screenshot verification passed.',
        }
        order = PaymentOrder.objects.create(
            attendee=self.attendee,
            event=self.event,
            organizer=self.organizer,
            ticket_type='VIP',
            quantity=1,
            unit_price=Decimal('2500'),
            total_amount=Decimal('2500'),
            status='pending_payment',
        )
        screenshot = SimpleUploadedFile('pay.jpg', b'fake-image-bytes', content_type='image/jpeg')
        self.client.force_login(self.attendee)
        response = self.client.post(
            f'/api/attendee/payment-orders/{order.id}/verify-screenshot/',
            data={'screenshot': screenshot},
        )
        self.assertEqual(response.status_code, 200)
        body = b''.join(response.streaming_content).decode()
        self.assertIn('pending_approval', body)
        order.refresh_from_db()
        self.assertEqual(order.status, 'manual_review')
        self.assertTrue(order.screenshot_verified)
        self.assertTrue(order.screenshot_data.startswith('data:image/'))
        self.assertFalse(Ticket.objects.filter(attendee=self.attendee).exists())
        self.assertEqual(OrganizerNotification.objects.filter(payment_order=order).count(), 1)
        self.assertEqual(AttendeeNotification.objects.filter(payment_order=order).count(), 1)

    @patch('payments.order_views.analyze_payment_screenshot')
    def test_verify_screenshot_routes_to_organizer_on_ocr_fail(self, mock_analyze):
        mock_analyze.return_value = {
            'success': False,
            'ocr_text': 'KES 500 paid to Someone Else',
            'notes': 'Payment amount does not match.',
        }
        order = PaymentOrder.objects.create(
            attendee=self.attendee,
            event=self.event,
            organizer=self.organizer,
            ticket_type='Regular',
            quantity=1,
            unit_price=Decimal('1000'),
            total_amount=Decimal('1000'),
            status='pending_payment',
        )
        screenshot = SimpleUploadedFile('pay.jpg', b'fake-image-bytes', content_type='image/jpeg')
        self.client.force_login(self.attendee)
        response = self.client.post(
            f'/api/attendee/payment-orders/{order.id}/verify-screenshot/',
            data={'screenshot': screenshot},
        )
        self.assertEqual(response.status_code, 200)
        body = b''.join(response.streaming_content).decode()
        self.assertIn('pending_approval', body)
        order.refresh_from_db()
        self.assertEqual(order.status, 'manual_review')
        self.assertFalse(order.screenshot_verified)
        self.assertFalse(Ticket.objects.filter(attendee=self.attendee).exists())
        self.assertEqual(OrganizerNotification.objects.filter(payment_order=order).count(), 1)

    def test_payment_order_rejects_mismatched_organizer(self):
        other_organizer = User.objects.create_user(
            username='org3', email='org3@test.com', password='pass12345', role='organizer',
        )
        with self.assertRaises(ValidationError):
            PaymentOrder.objects.create(
                attendee=self.attendee,
                event=self.event,
                organizer=other_organizer,
                ticket_type='Regular',
                quantity=1,
                unit_price=Decimal('1000'),
                total_amount=Decimal('1000'),
                status='pending_payment',
            )

    def test_checkout_api_fulfills_manual_review_order(self):
        order = PaymentOrder.objects.create(
            attendee=self.attendee,
            event=self.event,
            organizer=self.organizer,
            ticket_type='Regular',
            quantity=1,
            unit_price=Decimal('1000'),
            total_amount=Decimal('1000'),
            status='manual_review',
        )
        self.client.force_login(self.attendee)
        response = self.client.post(
            '/api/bookings/checkout/',
            data=f'{{"payment_order_id": {order.id}}}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(Ticket.objects.filter(attendee=self.attendee).exists())

    def test_organizer_notifications_api(self):
        order = PaymentOrder.objects.create(
            attendee=self.attendee,
            event=self.event,
            organizer=self.organizer,
            ticket_type='Regular',
            quantity=1,
            unit_price=Decimal('1000'),
            total_amount=Decimal('1000'),
            status='manual_review',
        )
        OrganizerNotification.objects.create(
            organizer=self.organizer,
            payment_order=order,
            title='Test',
            message='Approve payment',
            requires_action=True,
        )
        self.client.force_login(self.organizer)
        response = self.client.get('/api/organizer/notifications/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['notifications']), 1)

    @patch.dict('os.environ', {
        'MPESA_ENVIRONMENT': 'sandbox',
        'MPESA_CONSUMER_KEY': 'test-key',
        'MPESA_CONSUMER_SECRET': 'test-secret',
        'MPESA_SHORTCODE': '174379',
        'MPESA_PASSKEY': 'test-passkey',
        'MPESA_CALLBACK_URL': 'https://example.com/api/payments/mpesa/stk-callback/',
    })
    @patch('payments.order_views.MpesaClient.stk_push')
    def test_stk_push_initiates_order(self, mock_stk_push):
        mock_stk_push.return_value = {
            'ResponseCode': '0',
            'CheckoutRequestID': 'ws_CO_123',
            'MerchantRequestID': 'mr_123',
        }
        order = PaymentOrder.objects.create(
            attendee=self.attendee,
            event=self.event,
            organizer=self.organizer,
            ticket_type='Regular',
            quantity=1,
            unit_price=Decimal('1000'),
            total_amount=Decimal('1000'),
            status='pending_payment',
        )
        self.client.force_login(self.attendee)
        response = self.client.post(
            f'/api/attendee/payment-orders/{order.id}/stk-push/',
            data='{"phone": "254708374149"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['success'])
        order.refresh_from_db()
        self.assertEqual(order.checkout_request_id, 'ws_CO_123')
        self.assertEqual(order.stk_status, 'initiated')
        self.assertEqual(order.payment_rail, 'stk_platform')

    @patch.dict('os.environ', {
        'MPESA_ENVIRONMENT': 'sandbox',
        'MPESA_CONSUMER_KEY': 'test-key',
        'MPESA_CONSUMER_SECRET': 'test-secret',
        'MPESA_SHORTCODE': '174379',
        'MPESA_PASSKEY': 'test-passkey',
        'MPESA_CALLBACK_URL': 'https://example.com/api/payments/mpesa/stk-callback/',
    })
    def test_stk_callback_fulfills_order(self):
        order = PaymentOrder.objects.create(
            attendee=self.attendee,
            event=self.event,
            organizer=self.organizer,
            ticket_type='Regular',
            quantity=1,
            unit_price=Decimal('1000'),
            total_amount=Decimal('1000'),
            status='verifying',
            payment_rail='stk_platform',
            checkout_request_id='ws_CO_456',
            stk_status='initiated',
        )
        payload = {
            'Body': {
                'stkCallback': {
                    'CheckoutRequestID': 'ws_CO_456',
                    'ResultCode': 0,
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'MpesaReceiptNumber', 'Value': 'QAB123XYZ'},
                        ],
                    },
                },
            },
        }
        response = self.client.post(
            '/api/payments/mpesa/stk-callback/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual(order.status, 'completed')
        self.assertEqual(order.stk_status, 'success')
        self.assertEqual(order.mpesa_receipt, 'QAB123XYZ')
        self.assertEqual(self.event.available_seats, 99)
        self.assertTrue(Ticket.objects.filter(attendee=self.attendee).exists())

    def test_reject_manual_review_order(self):
        order = PaymentOrder.objects.create(
            attendee=self.attendee,
            event=self.event,
            organizer=self.organizer,
            ticket_type='Regular',
            quantity=1,
            unit_price=Decimal('1000'),
            total_amount=Decimal('1000'),
            status='manual_review',
            submitted_mpesa_name='JOHN DOE',
        )
        self.client.force_login(self.organizer)
        response = self.client.post(f'/api/organizer/payment-orders/{order.id}/reject/')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'rejected')


class ScreenshotVerifierTests(TestCase):
    def test_amount_match(self):
        ok, amt = _amount_matches(Decimal('1500'), [Decimal('1500'), Decimal('100')])
        self.assertTrue(ok)

    def test_fuzzy_name_match(self):
        ok, _ = _fuzzy_name_match('EventHub Digital', 'Paid to EVENTHUB DIGITAL successfully')
        self.assertTrue(ok)

    @patch('payments.screenshot_verifier.extract_text_from_image')
    def test_verify_screenshot_success(self, mock_ocr):
        mock_ocr.return_value = 'KES 1,500 paid to EventHub Digital confirmed'
        mock_file = MagicMock()
        result = verify_screenshot(mock_file, 'EventHub Digital', Decimal('1500'), ['123456'])
        self.assertTrue(result['success'])
        self.assertTrue(result['amount_matched'])

    @patch('payments.screenshot_verifier.extract_text_from_image')
    def test_verify_screenshot_failure(self, mock_ocr):
        mock_ocr.return_value = 'KES 500 paid to Someone Else'
        mock_file = MagicMock()
        result = verify_screenshot(mock_file, 'EventHub Digital', Decimal('1500'), [])
        self.assertFalse(result['success'])
