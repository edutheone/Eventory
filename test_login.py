import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import authenticate
from django.test import Client
from accounts.models import User

def run_test():
    client = Client()
    response = client.post('/admin/login/submit/', {
        'username': 'event',
        'password': 'event123'
    }, follow=True)

    print(f"Status code: {response.status_code}")
    print(f"Redirect chain: {response.redirect_chain}")
    print(f"Final URL: {response.request['PATH_INFO']}")
    print(f"Response content length: {len(response.content)}")

    # Check authentication
    user = authenticate(username='event', password='event123')
    print(f"\nDirect authentication: {'Success' if user else 'Failed'}")
    if user:
        print(f"User: {user.username}, Staff: {user.is_staff}")

    # Try to login and get session
    response2 = client.post('/admin/login/submit/', {
        'username': 'event',
        'password': 'event123'
    })
    print(f"\nLogin response status: {response2.status_code}")
    print(f"Location header: {response2.get('Location', 'No location')}")

if __name__ == '__main__':
    run_test()

