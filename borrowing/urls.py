from django.urls import path

from .views import (
    BorrowBookView,
    BorrowHistoryView,
    BorrowListView,
    ReturnBookView,
    ReserveBookView,
    ReservationListView,
    CancelReservationView,
)


app_name = "borrowing"

urlpatterns = [
    path("", BorrowListView.as_view(), name="borrow_list"),
    path("history/", BorrowHistoryView.as_view(), name="borrow_history"),
    path("borrow/<int:book_id>/", BorrowBookView.as_view(), name="borrow_book"),
    path("return/<int:pk>/", ReturnBookView.as_view(), name="return_book"),
    path("reserve/<int:book_id>/", ReserveBookView.as_view(), name="reserve_book"),
    path("reservations/", ReservationListView.as_view(), name="reservation_list"),
    path("reservations/cancel/<int:pk>/", CancelReservationView.as_view(), name="cancel_reservation"),
]
