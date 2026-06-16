import requests
from bs4 import BeautifulSoup

response = requests.get('http://127.0.0.1:8000/')
soup = BeautifulSoup(response.text, 'html.parser')

# Find navbar
navbar = soup.find('header', class_='attendee-navbar')
if navbar:
    print("✅ Navbar found with class 'attendee-navbar'")
    print(f"Navbar classes: {navbar.get('class')}")
else:
    print("❌ Navbar not found with class 'attendee-navbar'")
    # Check for any header
    header = soup.find('header')
    if header:
        print(f"Header found but with classes: {header.get('class')}")
    else:
        print("No header element found")
