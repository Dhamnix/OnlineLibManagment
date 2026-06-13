from django.apps import AppConfig


class BorrowingConfig(AppConfig):
    name = 'borrowing'

    def ready(self):
        # Import signal handlers to ensure they are registered
        try:
            import borrowing.signals  # noqa: F401
        except Exception:
            # In production, log the exception. Keep ready() resilient to import errors.
            pass
