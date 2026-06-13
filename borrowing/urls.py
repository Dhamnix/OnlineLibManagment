from django.urls import path

from .views import BorrowBookView, BorrowHistoryView, BorrowListView, ReturnBookView


app_name = "borrowing"

urlpatterns = [
    path("", BorrowListView.as_view(), name="borrow_list"),
    path("history/", BorrowHistoryView.as_view(), name="borrow_history"),
    path("borrow/<int:book_id>/", BorrowBookView.as_view(), name="borrow_book"),
    path("return/<int:pk>/", ReturnBookView.as_view(), name="return_book"),
]
