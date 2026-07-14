# borrowing/urls.py
from django.urls import path
from .views import (
    RequestBorrowView,
    BorrowHistoryView,
    BorrowListView,
    ReturnBookView,
    ReserveBookView,
    ReservationListView,
    CancelReservationView,
    FineListView,
    PayFineView,
    AdminBorrowListView,
    AdminBorrowRequestsView,
    ApproveBorrowView,
    RejectBorrowView,
    AdminReservationListView,
    AdminFineListView,  
)

app_name = "borrowing"

urlpatterns = [
    path("", BorrowListView.as_view(), name="borrow_list"),
    path("history/", BorrowHistoryView.as_view(), name="borrow_history"),
    
    # User: request to borrow
    path("request/<int:book_id>/", RequestBorrowView.as_view(), name="request_borrow"),
    
    # Reservations
    path("reserve/<int:book_id>/", ReserveBookView.as_view(), name="reserve_book"),
    path("reservations/", ReservationListView.as_view(), name="reservation_list"),
    path("reservations/cancel/<int:pk>/", CancelReservationView.as_view(), name="cancel_reservation"),
    
    # Fines
    path("fines/", FineListView.as_view(), name="fine_list"),
    path("fines/pay/<int:pk>/", PayFineView.as_view(), name="pay_fine"),
    
    # Admin: borrow request management
    path("admin/requests/", AdminBorrowRequestsView.as_view(), name="admin_borrow_requests"),
    path("admin/approve/<int:pk>/", ApproveBorrowView.as_view(), name="approve_borrow"),
    path("admin/reject/<int:pk>/", RejectBorrowView.as_view(), name="reject_borrow"),
    path("admin/return/<int:pk>/", ReturnBookView.as_view(), name="return_book"),
    
    # Admin: lists
    path("admin/borrowings/", AdminBorrowListView.as_view(), name="admin_borrow_list"),
    path("admin/reservations/", AdminReservationListView.as_view(), name="admin_reservation_list"),
    path("admin/fines/", AdminFineListView.as_view(), name="admin_fine_list"),
]