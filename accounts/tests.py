import json

from django.contrib.auth import get_user_model
from django.test import TestCase


class AccountAPITests(TestCase):
    def post_json(self, path, payload, token=None):
        headers = {}
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type='application/json',
            **headers,
        )

    def put_json(self, path, payload, token=None):
        headers = {}
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.client.put(
            path,
            data=json.dumps(payload),
            content_type='application/json',
            **headers,
        )

    def test_organizer_registration_requires_organization_name(self):
        response = self.post_json('/api/organizer/auth/register/', {
            'username': 'organizer',
            'email': 'organizer@example.com',
            'password': 'StrongPass123!',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('organization_name', response.json()['errors'])

    def test_organizer_can_register_login_and_update_profile(self):
        register_response = self.post_json('/api/organizer/auth/register/', {
            'username': 'organizer',
            'email': 'organizer@example.com',
            'password': 'StrongPass123!',
            'organization_name': 'Bright Events',
        })

        self.assertEqual(register_response.status_code, 201)
        register_data = register_response.json()
        self.assertEqual(register_data['user']['role'], 'organizer')
        self.assertEqual(register_data['user']['organization_name'], 'Bright Events')
        self.assertIn('access', register_data)
        self.assertIn('refresh', register_data)

        login_response = self.post_json('/api/organizer/auth/login/', {
            'username': 'organizer',
            'password': 'StrongPass123!',
        })

        self.assertEqual(login_response.status_code, 200)
        access = login_response.json()['access']

        profile_response = self.put_json('/api/organizer/profile/update/', {
            'first_name': 'Yvonne',
            'organization_name': 'Bright Events Ltd',
        }, token=access)

        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile_response.json()['user']['first_name'], 'Yvonne')
        self.assertEqual(profile_response.json()['user']['organization_name'], 'Bright Events Ltd')

    def test_attendee_cannot_login_to_organizer_portal(self):
        User = get_user_model()
        User.objects.create_user(
            username='attendee',
            email='attendee@example.com',
            password='StrongPass123!',
            role='attendee',
        )

        response = self.post_json('/api/organizer/auth/login/', {
            'username': 'attendee',
            'password': 'StrongPass123!',
        })

        self.assertEqual(response.status_code, 403)

    def test_refresh_and_logout_token_flow(self):
        register_response = self.post_json('/api/auth/register/', {
            'username': 'attendee',
            'email': 'attendee@example.com',
            'password': 'StrongPass123!',
            'role': 'attendee',
        })
        refresh = register_response.json()['refresh']
        access = register_response.json()['access']

        status_response = self.client.get(
            '/api/auth/check-status/',
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()['role'], 'attendee')

        refresh_response = self.post_json('/api/auth/refresh-token/', {'refresh': refresh})
        self.assertEqual(refresh_response.status_code, 200)
        new_access = refresh_response.json()['access']

        logout_response = self.post_json('/api/auth/logout/', {}, token=new_access)
        self.assertEqual(logout_response.status_code, 200)

        status_after_logout = self.client.get(
            '/api/auth/check-status/',
            HTTP_AUTHORIZATION=f'Bearer {new_access}',
        )
        self.assertEqual(status_after_logout.status_code, 401)

    def test_google_oauth_success_new_user(self):
        from unittest.mock import patch
        with patch('google.oauth2.id_token.verify_oauth2_token') as mock_verify:
            mock_verify.return_value = {
                'email': 'newgoogleuser@example.com',
                'sub': 'google_123456789',
                'given_name': 'New',
                'family_name': 'GoogleUser'
            }
            
            response = self.post_json('/api/auth/google/', {
                'credential': 'fake_credential_token',
                'role': 'attendee'
            })
            
            self.assertEqual(response.status_code, 200) # Since it resolves/returns tokens directly
            data = response.json()
            self.assertEqual(data['user']['email'], 'newgoogleuser@example.com')
            self.assertEqual(data['user']['role'], 'attendee')
            self.assertIn('access', data)
            
            # Check db association
            User = get_user_model()
            user = User.objects.get(email='newgoogleuser@example.com')
            self.assertEqual(user.google_id, 'google_123456789')

    def test_google_oauth_success_existing_user_by_email(self):
        User = get_user_model()
        existing_user = User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='Password123!',
            role='attendee'
        )
        
        from unittest.mock import patch
        with patch('google.oauth2.id_token.verify_oauth2_token') as mock_verify:
            mock_verify.return_value = {
                'email': 'existing@example.com',
                'sub': 'google_987654321',
                'given_name': 'Existing',
                'family_name': 'User'
            }
            
            response = self.post_json('/api/auth/google/', {
                'credential': 'fake_credential_token',
                'role': 'attendee'
            })
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['user']['id'], existing_user.id)
            
            # Verify google_id association
            existing_user.refresh_from_db()
            self.assertEqual(existing_user.google_id, 'google_987654321')

    def test_avatar_upload_success(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='uploaduser',
            email='upload@example.com',
            password='StrongPass123!',
            role='attendee'
        )
        login_response = self.post_json('/api/auth/login/', {
            'username': 'uploaduser',
            'password': 'StrongPass123!',
        })
        self.assertEqual(login_response.status_code, 200)
        access_token = login_response.json()['access']

        from django.core.files.uploadedfile import SimpleUploadedFile
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
            b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
            b'\x02\x4c\x01\x00\x3b'
        )
        avatar_file = SimpleUploadedFile("avatar.gif", small_gif, content_type="image/gif")

        response = self.client.post(
            '/api/profile/upload-avatar/',
            {'avatar': avatar_file},
            HTTP_AUTHORIZATION=f'Bearer {access_token}'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('Avatar uploaded successfully.', data['message'])
        self.assertIn('avatar', data['user']['avatar_url'])
        self.assertTrue(data['user']['avatar_url'].endswith('.gif'))

        user.refresh_from_db()
        self.assertTrue(user.avatar)
        self.assertEqual(user.avatar_url, '')
        self.assertEqual(user.get_avatar_url(), user.avatar.url)

    def test_google_oauth_syncs_picture(self):
        from unittest.mock import patch
        with patch('google.oauth2.id_token.verify_oauth2_token') as mock_verify:
            mock_verify.return_value = {
                'email': 'picuser@example.com',
                'sub': 'google_pic_123',
                'given_name': 'Pic',
                'family_name': 'User',
                'picture': 'https://lh3.googleusercontent.com/a/some_photo_url'
            }
            
            response = self.post_json('/api/auth/google/', {
                'credential': 'fake_credential_token',
                'role': 'attendee'
            })
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['user']['avatar_url'], 'https://lh3.googleusercontent.com/a/some_photo_url')
            
            User = get_user_model()
            user = User.objects.get(email='picuser@example.com')
            self.assertEqual(user.avatar_url, 'https://lh3.googleusercontent.com/a/some_photo_url')
            self.assertEqual(user.get_avatar_url(), 'https://lh3.googleusercontent.com/a/some_photo_url')


from events.models import Event, Category
from bookings.models import Ticket
from django.utils import timezone

class AdminCheckinAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        # Create administrative user
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='Password123!',
            is_staff=True,
            is_superuser=True
        )
        # Create non-staff user
        self.regular_user = User.objects.create_user(
            username='regularuser',
            email='regular@example.com',
            password='Password123!',
            is_staff=False
        )
        # Create category and event
        self.category = Category.objects.create(name='Music')
        self.organizer = User.objects.create_user(
            username='orguser',
            email='org@example.com',
            password='Password123!',
            role='organizer'
        )
        self.event = Event.objects.create(
            title='Rock Concert',
            organizer=self.organizer,
            category=self.category,
            start_date=timezone.now() + timezone.timedelta(days=1),
            end_date=timezone.now() + timezone.timedelta(days=1, hours=3),
            venue='Arena 1',
            price=50.0,
            total_seats=100,
            available_seats=100,
            status='published'
        )
        # Create tickets
        self.ticket1 = Ticket.objects.create(
            ticket_number='TICKET1001',
            attendee=self.regular_user,
            event=self.event,
            billing_name='Alice Smith',
            billing_email='alice@example.com',
            billing_phone='1234567890',
            quantity=2,
            price=50.0,
            status='checked_in',
            checked_in_at=timezone.now()
        )
        self.ticket2 = Ticket.objects.create(
            ticket_number='TICKET1002',
            attendee=self.regular_user,
            event=self.event,
            billing_name='Bob Jones',
            billing_email='bob@example.com',
            billing_phone='0987654321',
            quantity=1,
            price=50.0,
            status='valid'
        )


    def test_checkin_endpoints_forbidden_for_non_staff(self):
        self.client.force_login(self.regular_user)
        response = self.client.get('/api/admin/checkins/stats/')
        self.assertEqual(response.status_code, 403)

    def test_checkin_stats(self):
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/admin/checkins/stats/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['stats']['total_events'], 1)
        self.assertEqual(data['stats']['total_tickets'], 2)
        self.assertEqual(data['stats']['checked_in'], 1)
        self.assertEqual(data['stats']['avg_attendance'], 50.0)

    def test_checkin_events(self):
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/admin/checkins/events/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['events']), 1)
        self.assertEqual(data['events'][0]['title'], 'Rock Concert')
        self.assertEqual(data['events'][0]['total_tickets'], 2)
        self.assertEqual(data['events'][0]['checked_in'], 1)

    def test_checkin_recent(self):
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/admin/checkins/recent/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['checkins']), 1)
        self.assertEqual(data['checkins'][0]['ticket_number'], 'TICKET1001')
        self.assertEqual(data['checkins'][0]['attendee_name'], 'Alice Smith')

    def test_checkin_event_details(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(f'/api/admin/checkins/event/{self.event.id}/details/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['details']['total_tickets'], 2)
        self.assertEqual(data['details']['checked_in'], 1)
        self.assertEqual(data['details']['not_checked_in'], 1)
        self.assertEqual(data['details']['attendance_rate'], 50.0)

    def test_checkin_event_timeline(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(f'/api/admin/checkins/event/{self.event.id}/timeline/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('labels', data)
        self.assertIn('values', data)

    def test_checkin_export(self):
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/admin/checkins/export/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('TICKET1001', response.content.decode())

    def test_checkin_event_export(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(f'/api/admin/checkins/event/{self.event.id}/export/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('TICKET1001', response.content.decode())


class AdminEventApprovalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='Password123!',
            is_staff=True,
            is_superuser=True
        )
        self.organizer = User.objects.create_user(
            username='orguser',
            email='org@example.com',
            password='Password123!',
            role='organizer'
        )
        self.category = Category.objects.create(name='Music', slug='music')
        self.event = Event.objects.create(
            title='Draft Event',
            organizer=self.organizer,
            category=self.category,
            start_date=timezone.now() + timezone.timedelta(days=1),
            end_date=timezone.now() + timezone.timedelta(days=1, hours=3),
            venue='Arena 1',
            price=50.0,
            total_seats=100,
            available_seats=100,
            status='pending'
        )

    def test_admin_approve_event_sets_published(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(f'/api/admin/events/{self.event.id}/approve/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Verify status in DB transitions directly to published
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, 'published')


