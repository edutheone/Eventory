# EventHub: Online Event Management and Ticketing System

## Overview
EventHub is a modern, responsive, and user-interactive Online Event Management and Ticketing System. It enables users to efficiently discover, book, and manage events through a centralized digital platform. Designed with accessibility and user experience in mind, the system is optimized for desktops, tablets, and mobile devices.

Whether you're an attendee looking for the next big event, an organizer planning to host one, or an administrator managing the platform, EventHub provides a seamless, intuitive, and visually appealing experience.

## Core Features
1. **Modern Landing Page**: A visually engaging homepage showcasing featured and upcoming events with interactive design elements and clear navigation.
2. **User Registration & Authentication**: Secure role-based access for Attendees, Organizers, and Administrators, with robust user profile management.
3. **Event Management Module**: Organizers can create, edit, and manage events, including details like date, venue, ticket types, pricing, and promotional banners.
4. **Ticket Booking System**: Seamless online ticket reservation with secure payment integration and generation of digital tickets (QR codes/reference numbers).
5. **Interactive Dashboards**: Personalized, real-time dashboards providing insights into ticket sales, attendance, bookings, and overall event performance.
6. **Notifications & Communication**: Automated alerts (email, in-app) for confirmations, reminders, event announcements, and support inquiries.
7. **Reviews & Feedback System**: Tools for attendees to rate and review events, helping organizers improve future experiences.
8. **Modern, Responsive Design**: A fully responsive interface with smooth animations and intuitive navigation, delivering a premium look and feel across all devices.

## Technology Stack
- **Backend**: Python, Django, Django REST Framework
- **Frontend**: HTML5, Vanilla CSS, JavaScript (Django Templates)
- **Database**: SQLite (default, configurable to PostgreSQL/MySQL)

## Project Structure
The repository is structured to cleanly separate the backend logic from frontend assets and templates:
- `backend/`: Contains the Django project configuration (`config/`) and installed applications (`accounts`, `bookings`, `events`, `notifications`, `reviews`).
- `frontend/`: Contains static assets (`static/css`, `static/js`) and HTML templates (`templates/`) organized by user role (`admin`, `attendee`, `organizer`, `shared`).

## Getting Started

### Prerequisites
- Python 3.10+
- `pip` (Python package installer)
- `virtualenv` (recommended)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd events-system
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # On Windows:
   python -m venv .venv
   .venv\Scripts\activate
   
   # On macOS/Linux:
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Apply database migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser (for admin access):**
   ```bash
   python manage.py createsuperuser
   ```
   Follow the prompts to set up your administrator account.

6. **Run the development server:**
   ```bash
   python manage.py runserver
   ```
   The application will be accessible at `http://localhost:8000/`.

## Usage
- **Attendees**: Register an account, browse events on the homepage, add tickets to your cart, and manage bookings from your personalized dashboard.
- **Organizers**: Register as an organizer, access the organizer dashboard to create events, manage ticket types, track sales, and communicate with attendees.
- **Administrators**: Log in with your superuser credentials to access the admin dashboard, where you can oversee users, events, payments, and platform settings.
