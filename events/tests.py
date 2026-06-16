from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from events.models import Event, Category, EventImage
from django.core.files.uploadedfile import SimpleUploadedFile
import json

User = get_user_model()



class EventPageTests(TestCase):
    def test_events_page_without_trailing_slash_redirects(self):
        response = self.client.get('/events')

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/events/')

    def test_events_page_with_trailing_slash_loads(self):
        response = self.client.get('/events/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Discover Amazing Events')


class OrganizerPortalRoutingTests(TestCase):
    def test_bookings_page_loads_correct_template(self):
        response = self.client.get('/organizer/bookings/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'organizer/bookings/bookings.html')

    def test_attendees_page_loads_correct_template(self):
        response = self.client.get('/organizer/attendees/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'organizer/attendees/attendees.html')

    def test_profile_page_loads_settings_template(self):
        response = self.client.get('/organizer/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'organizer/settings/settings.html')


class EventImageUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create organizer user
        self.organizer = User.objects.create_user(
            username='organizer1',
            email='org@example.com',
            password='Password123',
            role='organizer'
        )
        # Create category
        self.category = Category.objects.create(name='Music', slug='music')
        # Create event
        self.event = Event.objects.create(
            title='Music Concert',
            description='Enjoy live music.',
            category=self.category,
            organizer=self.organizer,
            start_date=timezone.now() + timedelta(days=5),
            end_date=timezone.now() + timedelta(days=5, hours=3),
            venue='Central Park',
            price=20.00,
            total_seats=100,
            available_seats=100
        )
        # Log in
        self.client.login(username='organizer1', password='Password123')

    def test_upload_valid_banner(self):
        image_content = b'fake_png_data'
        uploaded_file = SimpleUploadedFile(
            name='banner.png',
            content=image_content,
            content_type='image/png'
        )
        response = self.client.post(
            f'/api/organizer/events/{self.event.id}/upload-image/',
            {'image': uploaded_file}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        # Image URL should be either a /media/ path (local FS) or a data: URI (serverless fallback)
        image_url = data['image_url']
        self.assertTrue(
            image_url.startswith('/media/events/banners/banner_') or image_url.startswith('data:image/'),
            f"Unexpected image_url format: {image_url[:60]}"
        )

        # Verify db updated
        self.event.refresh_from_db()
        self.assertEqual(self.event.banner_image, data['image_url'])

    def test_upload_invalid_file_extension(self):
        uploaded_file = SimpleUploadedFile(
            name='document.pdf',
            content=b'pdf content',
            content_type='application/pdf'
        )
        response = self.client.post(
            f'/api/organizer/events/{self.event.id}/upload-image/',
            {'image': uploaded_file}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('Unsupported file extension', data['message'])

    def test_upload_gallery_images(self):
        img1 = SimpleUploadedFile('pic1.jpg', b'jpegdata1', content_type='image/jpeg')
        img2 = SimpleUploadedFile('pic2.svg', b'<svg></svg>', content_type='image/svg+xml')
        
        response = self.client.post(
            f'/api/organizer/events/{self.event.id}/upload-gallery/',
            {'gallery_0': img1, 'gallery_1': img2}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['images']), 2)
        
        # Verify db count
        self.assertEqual(self.event.images.count(), 2)

    def test_delete_gallery_image(self):
        # image is now a TextField – store a plain path string
        img_obj = EventImage.objects.create(event=self.event, image='events/gallery/pic.png')
        
        response = self.client.delete(
            f'/api/organizer/events/{self.event.id}/gallery/{img_obj.id}/delete/'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Verify db updated
        self.assertEqual(self.event.images.count(), 0)

    def test_get_event_detail_approved(self):
        self.event.status = 'approved'
        self.event.save()
        
        response = self.client.get(f'/api/organizer/events/{self.event.id}/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['id'], self.event.id)
        self.assertEqual(data['status'], 'approved')


