# books/urls.py

from django.urls import path

from .views import (
    BookCreateView,
    BookDeleteView,
    BookDetailView,
    BookListView,
    BookUpdateView,
    AdminBookListView, 
)

app_name = "books"

urlpatterns = [
    # Public routes (for regular users)
    path("", BookListView.as_view(), name="book_list"),
    
    # Admin routes
    path("admin/", AdminBookListView.as_view(), name="admin_book_list"),
    
    path("add/", BookCreateView.as_view(), name="book_create"),
    path("<int:pk>/", BookDetailView.as_view(), name="book_detail"),
    path("<int:pk>/edit/", BookUpdateView.as_view(), name="book_update"),
    path("<int:pk>/delete/", BookDeleteView.as_view(), name="book_delete"),
]