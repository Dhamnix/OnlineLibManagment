from django.apps import AppConfig


class NotifConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notif'
    verbose_name = 'Notifications'

    def ready(self):
        import notif.signals