from django.apps import AppConfig


class HansvietAdminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hansviet_admin'

    def ready(self):
        # Auto-create a default superuser for quick admin access if none exists.
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if not User.objects.filter(is_superuser=True).exists():
                User.objects.create_superuser(
                    username="admin",
                    email="admin@example.com",
                    password="admin123",
                )
        except Exception:
            # Avoid breaking startup if DB is not migrated yet.
            pass
