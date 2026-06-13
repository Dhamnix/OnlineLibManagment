from django.contrib import admin
from django.db.models import Avg

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "rating", "created_at", "comment_preview")
    list_filter = ("rating", "created_at", "book")
    search_fields = ("user__username", "book__title", "comment")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    
    fieldsets = (
        ("Review Information", {
            "fields": ("user", "book", "rating")
        }),
        ("Content", {
            "fields": ("comment",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    def comment_preview(self, obj):
        """Display a preview of the comment."""
        if obj.comment:
            return obj.comment[:50] + "..." if len(obj.comment) > 50 else obj.comment
        return "No comment"
    comment_preview.short_description = "Comment Preview"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related("user", "book")
