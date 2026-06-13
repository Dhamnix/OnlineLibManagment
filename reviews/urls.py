from django.urls import path

from .views import ReviewCreateView, ReviewDeleteView, ReviewUpdateView

app_name = "reviews"

urlpatterns = [
    path(
        "book/<int:book_pk>/add/",
        ReviewCreateView.as_view(),
        name="review_add"
    ),
    path(
        "book/<int:book_pk>/edit/",
        ReviewUpdateView.as_view(),
        name="review_edit"
    ),
    path(
        "book/<int:book_pk>/delete/",
        ReviewDeleteView.as_view(),
        name="review_delete"
    ),
]
