# Online Library Management (Django)

A simple, educational Online Library Management System built with Django. It supports user accounts, book catalog management, borrowing & reservation workflows, fines and payments, reviews & ratings, notifications, dashboards, and a simple recommendation engine.

This README summarizes the codebase, features, setup, important commands, and developer notes.

---

## Project Overview

This project is a university-style library management web application implemented in Django. It demonstrates typical web application patterns: models, forms, class-based views, templates, signals, management commands, and a small pluggable services layer (payments, notifications, recommendations).

Primary responsibilities implemented:

- User management: registration, login, profile, roles (Admin / Member)
- Book management: add, edit, delete books, available copies tracking
- Search & filters: title search, author/genre/year filters
- Borrowing system: borrow, return, due dates, status
- Reservation system: reserve unavailable books and reservation lifecycle
- Fine system: late-return penalties, fine calculation, tracking
- Dashboards: user and admin dashboards showing relevant data
- Reviews & ratings: create/edit/delete reviews, average rating
- Notifications: email notifications for reservations and due-date reminders (management command)
- Recommendations: simple "Recommended For You" and "Similar Books" logic using ORM
- Payments: a pluggable payment layer (DummyGateway by default) and payment history

---

## Tech stack

- Python 3.10+
- Django 4+/5 compatible code (project was bootstrapped with Django 6 docs originally)
- SQLite (development); PostgreSQL recommended for production

Key apps in repository:
- `accounts` — custom user model and auth
- `books` — book catalog
- `borrowing` — borrow/reservation/fines
- `reviews` — review & rating subsystem
- `dashboard` — user + admin dashboards
- `notifications` — email sending helpers
- `payments` — payment models & gateway abstraction
- `recommendations` — recommendation services

---

## Quick start (development)

1. Clone the repository and create a Python virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# or
source .venv/bin/activate  # macOS / Linux
```

2. Install dependencies (add your own requirements.txt if present):

```bash
pip install -r requirements.txt  # if requirements.txt exists
# otherwise install Django and any libs used
pip install django
```

3. Configure settings via environment variables (recommended):

- `DJANGO_SECRET_KEY` — required in production
- `DJANGO_DEBUG` — `True` or `False`
- `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`

4. Apply migrations and create a superuser:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

5. Run the development server:

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

---

## Important management commands

- send_due_notifications
  - Purpose: send due-date reminders (3 days and 1 day before due date) and overdue notifications for borrowings that haven't been returned.
  - Usage:
    - Dry run (no emails, no DB changes):
      ```bash
      python manage.py send_due_notifications --dry-run
      ```
    - Real run:
      ```bash
      python manage.py send_due_notifications
      ```
  - Scheduling: run daily via cron or a scheduled task.

- Standard Django management commands also apply (migrate, createsuperuser, test, etc.).

---

## Registration & Roles (security note)

- The public registration form does not expose role selection. All newly registered users are assigned `role = MEMBER` server-side and placed into the `Member` Group automatically.
- Admin / librarian accounts should be created by site administrators via the Django admin or `createsuperuser` (admin-only flows remain unchanged).

This prevents privilege escalation via the registration UI.

---

## Notifications

- Notification helper functions live in `notifications/services.py` and provide:
  - `send_email(...)` — wrapper around Django email
  - `send_borrow_notification(...)` — sent when a borrow is created (signals or services can call it)
  - `send_reserved_available_notification(...)` — sent when a reserved book becomes available
  - `send_due_approaching_notifications(...)` and `send_overdue_notifications(...)` are provided for batch runs but the official mechanism for reminders in this project is the management command `send_due_notifications` (see above).

- The `send_due_notifications` management command uses a `DueNotification` model to track which notifications have been sent to avoid duplicates.

- By default, emails are sent synchronously from the management command; for heavy production use replace with an async worker (Celery, RQ) and use `transaction.on_commit` to enqueue tasks.

---

## Payments

- Payments are implemented under the `payments` app.
- The system uses a gateway abstraction (`payments.services.PaymentGateway`). A `DummyGateway` is provided for development and testing; it immediately marks payments as completed.
- For production, implement a real gateway adapter and set the `PAYMENT_GATEWAY` setting to the import path of your gateway class.
- Payments are recorded in `payments.models.Payment` and linked to `borrowing.models.Fine`.

---

## Recommendations

- Basic recommendation logic is under `recommendations/services.py` and is used by the user dashboard.
- It recommends books based on user's borrowing history, favored genres, co-borrowed books, and overall popularity.
- This is intentionally simple and implemented using the Django ORM only.

---

## Tests

- A test module exists for borrowing flows (see `borrowing/tests.py`). Add tests for payments, notifications and recommendations as needed.

Run tests:

```bash
python manage.py test
```

---

## Developer notes and known caveats

- Database: The project uses SQLite for development; switch to PostgreSQL in production for JSONField, concurrency, and robustness.

- Emails: For local development configure Django's console or locmem email backend to observe emails. Example in `settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

- Payments: Current flow uses synchronous processing (DummyGateway). For any real payment gateway you should implement async processing and webhook verification.

- Notifications: The management command avoids duplicates using the `DueNotification` model. It runs without Celery so it is appropriate for environments where Celery is not available.

- Security: Registration no longer exposes role selection. Ensure `DJANGO_SECRET_KEY` and `DEBUG=False` in production.

- Permissions: The project mixes role checks and Django permissions in some places. Consider standardizing on Django Groups & Permissions and assigning permissions via `accounts/signals.py`.

---

## File map (high-level)

- `OnlineLibManagment/` — project settings and URL configuration
- `accounts/` — custom user model, registration & auth
- `books/` — book models, views, forms, templates
- `borrowing/` — Borrow, Reservation, Fine, DueNotification, services, views, management commands
- `reviews/` — review model & views
- `dashboard/` — user and admin dashboards
- `notifications/` — email helper services
- `payments/` — payment models, views, services
- `recommendations/` — recommendation services

---

## Contribution

Contributions are welcome. Typical workflow:

1. Fork the repository.
2. Create a feature branch.
3. Add tests for new/changed behavior.
4. Submit a PR with a clear description and motivation.

Please follow the project's coding style and run tests before opening a PR.

---

## License

This repository is provided for educational use. Add your preferred license file if you intend to redistribute.

---

If you want, I can also:
- Add an example `docker-compose` for local dev (not requested).
- Add CI test configuration or simple unit tests for notifications and payments.

Enjoy working with the project! If you want a shorter README or one tailored specifically to deploy to a host (Heroku, Render, etc.), say which target and I'll adapt it. 