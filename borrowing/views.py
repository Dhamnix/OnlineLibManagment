from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from books.models import Book
from .models import Borrow


class BorrowListView(LoginRequiredMixin, ListView):
    model = Borrow
    template_name = "borrowing/borrow_list.html"
    context_object_name = "borrowings"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        # Librarians/admins see all borrowings, members see only their own
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            return Borrow.objects.all()
        return Borrow.objects.filter(user=user)


class BorrowBookView(LoginRequiredMixin, View):
    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        if book.available_copies <= 0:
            messages.error(request, "This book is currently out of stock and cannot be borrowed.", extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)
        
        due_date = timezone.now() + timezone.timedelta(days=14)
        return render(request, "borrowing/borrow_confirm.html", {"book": book, "due_date": due_date})

    def post(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        
        try:
            with transaction.atomic():
                # Lock the book row to prevent race conditions
                book_to_borrow = Book.objects.select_for_update().get(pk=book_id)
                if book_to_borrow.available_copies <= 0:
                    messages.error(request, "This book is currently out of stock and cannot be borrowed.", extra_tags="danger")
                    return redirect("books:book_detail", pk=book_id)
                
                # Reduce available copies
                book_to_borrow.available_copies -= 1
                book_to_borrow.save()
                
                # Create Borrow record
                Borrow.objects.create(
                    user=request.user,
                    book=book_to_borrow,
                    status=Borrow.StatusChoices.BORROWED
                )
                
            messages.success(request, f"You have successfully borrowed '{book.title}'.")
            return redirect("borrowing:borrow_list")
        except Exception:
            messages.error(request, "An error occurred while borrowing the book. Please try again.", extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)


class ReturnBookView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user = request.user
        # Allow admins to return any borrowing, members only their own
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            borrow = get_object_or_404(Borrow, pk=pk)
        else:
            borrow = get_object_or_404(Borrow, pk=pk, user=user)

        if borrow.status == Borrow.StatusChoices.RETURNED:
            messages.warning(request, "This book has already been returned.")
            return redirect("borrowing:borrow_list")

        try:
            with transaction.atomic():
                # Update status and return date
                borrow.status = Borrow.StatusChoices.RETURNED
                borrow.return_date = timezone.now()
                borrow.save()
                
                # Lock book to increment copies safely
                book = Book.objects.select_for_update().get(pk=borrow.book.pk)
                book.available_copies += 1
                book.save()
                
            messages.success(request, f"You have successfully returned '{borrow.book.title}'.")
        except Exception:
            messages.error(request, "An error occurred while returning the book. Please try again.", extra_tags="danger")
            
        return redirect("borrowing:borrow_list")


class BorrowHistoryView(LoginRequiredMixin, ListView):
    model = Borrow
    template_name = "borrowing/borrow_history.html"
    context_object_name = "borrowings"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        # Librarians/admins see all borrowings, members see only their own
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            queryset = Borrow.objects.all()
        else:
            queryset = Borrow.objects.filter(user=user)

        status_filter = self.request.GET.get("status", "").strip().lower()
        now = timezone.now()

        if status_filter == "active":
            queryset = queryset.filter(status=Borrow.StatusChoices.BORROWED, due_date__gte=now)
        elif status_filter == "returned":
            queryset = queryset.filter(status=Borrow.StatusChoices.RETURNED)
        elif status_filter == "overdue":
            queryset = queryset.filter(status=Borrow.StatusChoices.BORROWED, due_date__lt=now)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status = self.request.GET.get("status", "").strip().lower()
        context["current_status"] = status
        
        # Add a helper for templates to check if a borrowing is overdue
        context["now"] = timezone.now()
        return context
