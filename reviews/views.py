from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, UpdateView

from books.models import Book
from .forms import ReviewForm
from .models import Review
from notif.services import notify_review_added, notify_review_updated, create_notification
from notif.models import Notification


class ReviewCreateView(LoginRequiredMixin, CreateView):
    model = Review
    form_class = ReviewForm
    template_name = "reviews/review_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.book = get_object_or_404(Book, pk=kwargs.get("book_pk"))
        
        existing_review = Review.objects.filter(
            user=request.user,
            book=self.book
        ).first()
        
        if existing_review:
            messages.warning(
                request,
                "You have already reviewed this book. Edit your review instead."
            )
            return redirect("reviews:review_edit", book_pk=self.book.pk)
        
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.book = self.book
        response = super().form_valid(form)
        notify_review_added(self.request.user, self.book, form.instance.rating)
        messages.success(self.request, "Review added successfully!")
        return response

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.book.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = self.book
        return context


class ReviewUpdateView(LoginRequiredMixin, UpdateView):
    model = Review
    form_class = ReviewForm
    template_name = "reviews/review_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.book = get_object_or_404(Book, pk=kwargs.get("book_pk"))
        self.review = get_object_or_404(
            Review,
            user=request.user,
            book=self.book
        )
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.review

    def form_valid(self, form):
        response = super().form_valid(form)
        notify_review_updated(self.request.user, self.book, form.instance.rating)
        messages.success(self.request, "Review updated successfully!")
        return response

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.book.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = self.book
        context["is_update"] = True
        return context


class ReviewDeleteView(LoginRequiredMixin, DeleteView):
    model = Review

    def dispatch(self, request, *args, **kwargs):
        self.book = get_object_or_404(Book, pk=kwargs.get("book_pk"))
        self.review = get_object_or_404(
            Review,
            user=request.user,
            book=self.book
        )
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.review

    def delete(self, request, *args, **kwargs):
        create_notification(
            user=request.user,
            notification_type=Notification.Type.SYSTEM,
            title=f"🗑️ Review Deleted: {self.book.title}",
            message=f"You have deleted your review for '{self.book.title}'.",
            link=f"/books/{self.book.pk}/"
        )
        messages.success(request, "Review deleted successfully!")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.book.pk})