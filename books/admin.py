from django.contrib import admin

from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "genre",
        "publish_year",
        "total_copies",
        "available_copies",
    )
    search_fields = ("title", "author", "isbn")
    list_filter = ("genre", "publish_year")
    ordering = ("title",)

    fieldsets = (
        (
            "Book details",
            {
                "fields": (
                    "title",
                    "author",
                    "genre",
                    "description",
                    "publish_year",
                    "isbn",
                    "cover_image",
                )
            },
        ),
        (
            "Inventory",
            {
                "fields": (
                    "total_copies",
                    "available_copies",
                )
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is not None:
            return self.fieldsets

        # On create, available_copies defaults to total_copies at model save time.
        return (
            self.fieldsets[0],
            (
                "Inventory",
                {
                    "fields": (
                        "total_copies",
                    )
                },
            ),
        )
