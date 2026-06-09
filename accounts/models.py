from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUserManager(UserManager):
    """Manager for the custom user model.

    The project still authenticates by username, but email is required and
    unique so it can be trusted for account communication and lookup.
    """

    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError("The username must be set.")
        if not email:
            raise ValueError("The email address must be set.")

        email = self.normalize_email(email)
        username = self.model.normalize_username(username)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", CustomUser.Role.MEMBER)

        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", CustomUser.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if extra_fields.get("role") != CustomUser.Role.ADMIN:
            raise ValueError("Superuser must have role=ADMIN.")

        return self._create_user(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", _("Admin")
        MEMBER = "MEMBER", _("Member")

    # AbstractUser already provides username, first_name, last_name, password,
    # permissions, and activity fields. Email is redefined to enforce uniqueness.
    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(
        _("role"),
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.username
