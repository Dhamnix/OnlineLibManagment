from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings


class LibrarySettings(models.Model):
    """Global library system settings"""
    
    # ========== General Settings ==========
    site_name = models.CharField(max_length=100, default="OnlineLib")
    site_description = models.TextField(blank=True, default="Smart Library Management System")
    site_logo = models.ImageField(upload_to="settings/", blank=True, null=True)
    favicon = models.ImageField(upload_to="settings/", blank=True, null=True)
    
    # ========== Borrowing Settings ==========
    default_loan_days = models.PositiveIntegerField(
        default=14,
        help_text="Default loan period for books (days)"
    )
    max_loan_days = models.PositiveIntegerField(
        default=30,
        help_text="Maximum loan period (days)"
    )
    max_books_per_user = models.PositiveIntegerField(
        default=5,
        help_text="Maximum number of books a user can borrow simultaneously"
    )
    allow_auto_renew = models.BooleanField(
        default=False,
        help_text="Enable automatic loan renewal"
    )
    
    # ========== Fine Settings ==========
    fine_per_day = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        default=1.00,
        help_text="Fine amount per day overdue (USD)"
    )
    max_fine_amount = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=50.00,
        help_text="Maximum fine amount per book"
    )
    grace_period_days = models.PositiveIntegerField(
        default=0,
        help_text="Number of grace days before fines are applied"
    )
    
    # ========== Reservation Settings ==========
    reservation_expiry_days = models.PositiveIntegerField(
        default=3,
        help_text="Reservation validity period after availability notification (days)"
    )
    max_reservations_per_user = models.PositiveIntegerField(
        default=3,
        help_text="Maximum concurrent reservations per user"
    )
    
    # ========== Notification Settings ==========
    enable_email_notifications = models.BooleanField(
        default=True,
        help_text="Enable email notifications"
    )
    enable_sms_notifications = models.BooleanField(
        default=False,
        help_text="Enable SMS notifications"
    )
    due_reminder_days = models.PositiveIntegerField(
        default=3,
        help_text="Days before due date to send reminders"
    )
    
    # ========== Security Settings ==========
    require_email_verification = models.BooleanField(
        default=True,
        help_text="Require email verification for registration"
    )
    session_timeout_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Session timeout duration (minutes)"
    )
    max_login_attempts = models.PositiveIntegerField(
        default=5,
        help_text="Maximum failed login attempts"
    )
    
    # ========== Appearance Settings ==========
    primary_color = models.CharField(
        max_length=7, 
        default="#6366f1",
        help_text="Primary site color (HEX)"
    )
    secondary_color = models.CharField(
        max_length=7, 
        default="#10b981",
        help_text="Secondary site color (HEX)"
    )
    show_hero_section = models.BooleanField(
        default=True,
        help_text="Show hero section on home page"
    )
    
    # ========== Metadata ==========
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settings_updates"
    )
    
    class Meta:
        verbose_name = "Library Settings"
        verbose_name_plural = "Library Settings"
    
    def __str__(self):
        return f"Library Settings ({self.updated_at.strftime('%Y-%m-%d')})"
    
    @classmethod
    def get_settings(cls):
        """Get settings (auto-create if none exist)"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings