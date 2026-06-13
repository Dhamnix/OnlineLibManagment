from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, UpdateView

from books.models import Book
from .forms import ReviewForm
from .models import Review


class ReviewCreateView(LoginRequiredMixin, CreateView):
    model = Review
    form_class = ReviewForm
    template_name = "reviews/review_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.book = get_object_or_404(Book, pk=kwargs.get("book_pk"))
        
        # Check if user already has a review for this book
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
        messages.success(self.request, "Review added successfully!")
        return super().form_valid(form)

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
        messages.success(self.request, "Review updated successfully!")
        return super().form_valid(form)

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
        messages.success(request, "Review deleted successfully!")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.book.pk})


def get_book_average_rating(book_id):
    """Calculate and return average rating for a book."""
    average = Review.objects.filter(book_id=book_id).aggregate(
        avg_rating=Avg("rating")
    )["avg_rating"]
    
    return round(average, 1) if average else 0

