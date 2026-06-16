import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from events.models import Category, Event

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with upcoming events in Nairobi, Kenya'

    def handle(self, *args, **options):
        self.stdout.write('Seeding categories...')
        categories_data = [
            {'name': 'Holiday & Culture', 'description': 'National holidays, festivals, and cultural events', 'icon': 'globe'},
            {'name': 'Business & Tech', 'description': 'Conferences, expos, and professional networking', 'icon': 'briefcase'},
            {'name': 'Shopping & Lifestyle', 'description': 'Sales, trivia nights, social events, and food weeks', 'icon': 'shopping-bag'},
            {'name': 'Sports & Outdoor', 'description': 'Marathons, trail runs, hikes, and outdoor activities', 'icon': 'activity'},
            {'name': 'Art & Music', 'description': 'Concerts, art galleries, theatre, and dance', 'icon': 'music'},
        ]

        categories = {}
        for cat_data in categories_data:
            cat_slug = slugify(cat_data['name'])
            category, created = Category.objects.get_or_create(
                slug=cat_slug,
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'icon': cat_data['icon']
                }
            )
            categories[cat_slug] = category
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created category: {category.name}'))

        # Get or create a default organizer user
        self.stdout.write('Fetching or creating default organizer...')
        organizer, created = User.objects.get_or_create(
            username='nairobi_organizer',
            defaults={
                'email': 'organizer@eventhub.co.ke',
                'role': 'organizer',
                'phone': '+254700000000',
                'organization_name': 'Nairobi Events Council',
                'is_active': True
            }
        )
        if created:
            organizer.set_password('Nairobi2026!')
            organizer.save()
            self.stdout.write(self.style.SUCCESS(f'Created default organizer: {organizer.username}'))

        # Clean datetime helper
        def get_tz_datetime(year, month, day, hour, minute):
            return timezone.make_aware(datetime.datetime(year, month, day, hour, minute))

        self.stdout.write('Seeding events...')
        events_data = [
            {
                'title': 'Madaraka Day Celebrations 2026',
                'description': 'Kenya celebrates its self-rule with grand military parades, national flypasts, cultural performances, and patriotic speeches. A national holiday event open to the general public.',
                'category': categories['holiday-culture'],
                'start_date': get_tz_datetime(2026, 6, 1, 8, 0),
                'end_date': get_tz_datetime(2026, 6, 1, 17, 0),
                'venue': 'Nyayo National Stadium',
                'address': 'Aerodrome Road, Nairobi',
                'price': 0.00,
                'total_seats': 30000,
                'available_seats': 30000,
                'banner_image': 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&q=80&w=800',
                'status': 'published',
                'is_featured': True,
            },
            {
                'title': 'Global Data Festival & Kenya Space Expo Conference',
                'description': 'A premier gathering of regional and international experts focusing on data systems, data science, space intelligence, and space science innovations in Africa.',
                'category': categories['business-tech'],
                'start_date': get_tz_datetime(2026, 6, 2, 9, 0),
                'end_date': get_tz_datetime(2026, 6, 5, 18, 0),
                'venue': 'The Edge Hotel & Convention Center',
                'address': 'Convention Drive, Nairobi',
                'price': 15000.00,
                'total_seats': 500,
                'available_seats': 500,
                'banner_image': 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&q=80&w=800',
                'status': 'published',
                'is_featured': True,
            },
            {
                'title': 'Perishable Logistics Africa 2026',
                'description': 'Leading industry forum for cool chain management, logistics, air cargo, and transportation of fresh produce and pharmaceuticals across Africa and globally.',
                'category': categories['business-tech'],
                'start_date': get_tz_datetime(2026, 6, 4, 9, 0),
                'end_date': get_tz_datetime(2026, 6, 4, 17, 0),
                'venue': 'Nairobi Serena Hotel',
                'address': 'Processional Way, Nairobi',
                'price': 5000.00,
                'total_seats': 200,
                'available_seats': 200,
                'banner_image': 'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&q=80&w=800',
                'status': 'published',
                'is_featured': False,
            },
            {
                'title': 'Flower Logistics Africa 2026',
                'description': 'A specialized conference focused on temperature-controlled transport, cold chain best practices, and distribution network enhancements for Kenyas floriculture sector.',
                'category': categories['business-tech'],
                'start_date': get_tz_datetime(2026, 6, 5, 9, 0),
                'end_date': get_tz_datetime(2026, 6, 5, 17, 0),
                'venue': 'Nairobi Serena Hotel',
                'address': 'Processional Way, Nairobi',
                'price': 5000.00,
                'total_seats': 200,
                'available_seats': 200,
                'banner_image': 'https://images.unsplash.com/photo-1490750967868-88aa4486c946?auto=format&fit=crop&q=80&w=800',
                'status': 'published',
                'is_featured': False,
            },
            {
                'title': 'Sarit Mega Mid-Year Sale',
                'description': 'Experience the ultimate shopping event in Nairobi. Discover massive mid-year discount sales on household appliances, electronics, clothing, and artisanal foods.',
                'category': categories['shopping-lifestyle'],
                'start_date': get_tz_datetime(2026, 6, 4, 10, 0),
                'end_date': get_tz_datetime(2026, 6, 7, 20, 0),
                'venue': 'Sarit Centre Expo Hall',
                'address': 'Karuna Road, Westlands, Nairobi',
                'price': 0.00,
                'total_seats': 10000,
                'available_seats': 10000,
                'banner_image': 'https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&q=80&w=800',
                'status': 'published',
                'is_featured': True,
            },
            {
                'title': 'Nairobi Eco Trail Run + Walk 2026',
                'description': 'Join other eco-conscious runners and walkers for a morning trail through the beautiful Ngong Forest. Supporting local conservation efforts.',
                'category': categories['sports-outdoor'],
                'start_date': get_tz_datetime(2026, 6, 6, 6, 30),
                'end_date': get_tz_datetime(2026, 6, 6, 11, 30),
                'venue': 'Ngong Forest Sanctuary',
                'address': 'Ngong Road, Nairobi',
                'price': 1500.00,
                'total_seats': 1000,
                'available_seats': 1000,
                'banner_image': 'https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?auto=format&fit=crop&q=80&w=800',
                'status': 'published',
                'is_featured': False,
            },
            {
                'title': 'Nairobi International Cultural Festival',
                'description': 'A spectacular celebration showcasing diverse world cultures through traditional music, martial arts, culinary specialties, and national costume exhibitions.',
                'category': categories['holiday-culture'],
                'start_date': get_tz_datetime(2026, 6, 6, 10, 0),
                'end_date': get_tz_datetime(2026, 6, 6, 18, 0),
                'venue': 'TVET Grounds, Gigiri',
                'address': 'Gigiri Road, Nairobi',
                'price': 500.00,
                'total_seats': 2000,
                'available_seats': 2000,
                'banner_image': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&q=80&w=800',
                'status': 'published',
                'is_featured': True,
            },
            {
                'title': 'Ya Marafiki (Art & Music Social)',
                'description': 'An intimate social gathering celebrating underground local art, live acoustic performances, open mic sessions, and collaborative canvas painting.',
                'category': categories['art-music'],
                'start_date': get_tz_datetime(2026, 6, 6, 14, 0),
                'end_date': get_tz_datetime(2026, 6, 6, 22, 0),
                'venue': 'The Alchemist Bar',
                'address': 'Parklands Road, Westlands, Nairobi',
                'price': 1000.00,
                'total_seats': 400,
                'available_seats': 400,
                'banner_image': 'https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&q=80&w=800',
                'status': 'published',
                'is_featured': False,
            },
            {
                'title': 'Trivia Social: The World Tour',
                'description': 'Test your knowledge on geography, world history, and pop culture at this fun trivia social. Team up with friends and compete for amazing gift hampers.',
                'category': categories['shopping-lifestyle'],
                'start_date': get_tz_datetime(2026, 6, 11, 18, 30),
                'end_date': get_tz_datetime(2026, 6, 11, 21, 30),
                'venue': 'Kahoffee House',
                'address': 'Ngong Road, Nairobi',
                'price': 300.00,
                'total_seats': 80,
                'available_seats': 80,
                'banner_image': 'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?auto=format&fit=crop&q=80&w=800',
                'status': 'published',
                'is_featured': False,
            }
        ]

        for e_data in events_data:
            event_slug = slugify(e_data['title'])
            event, created = Event.objects.update_or_create(
                slug=event_slug,
                defaults={
                    'title': e_data['title'],
                    'description': e_data['description'],
                    'category': e_data['category'],
                    'organizer': organizer,
                    'start_date': e_data['start_date'],
                    'end_date': e_data['end_date'],
                    'venue': e_data['venue'],
                    'address': e_data['address'],
                    'price': e_data['price'],
                    'total_seats': e_data['total_seats'],
                    'available_seats': e_data['available_seats'],
                    'banner_image': e_data['banner_image'],
                    'status': e_data['status'],
                    'is_featured': e_data['is_featured']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created event: {event.title}'))
            else:
                self.stdout.write(f'Updated event: {event.title}')

        self.stdout.write(self.style.SUCCESS('Successfully seeded Nairobi upcoming events!'))
