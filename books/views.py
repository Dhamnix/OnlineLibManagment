from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Avg
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import BookForm
from .models import Book


class BookListView(ListView):
    """View for regular users - shows public book list"""
    model = Book
    template_name = "books/book_list.html"
    context_object_name = "books"
    paginate_by = 10

    def get_queryset(self):
        queryset = Book.objects.annotate(average_rating=Avg('reviews__rating'))
        search = self.request.GET.get("search", "").strip()
        author = self.request.GET.get("author", "").strip()
        genre = self.request.GET.get("genre", "").strip()
        year = self.request.GET.get("year", "").strip()

        if search:
            queryset = queryset.filter(title__icontains=search)
        if author:
            queryset = queryset.filter(author__icontains=author)
        if genre:
            queryset = queryset.filter(genre=genre)
        if year:
            queryset = queryset.filter(publish_year=year)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        search = self.request.GET.get("search", "").strip()
        author = self.request.GET.get("author", "").strip()
        genre = self.request.GET.get("genre", "").strip()
        year = self.request.GET.get("year", "").strip()

        context["search"] = search
        context["selected_author"] = author
        context["selected_genre"] = genre
        context["selected_year"] = year

        context["authors"] = (
            Book.objects.exclude(author="")
            .order_by("author")
            .values_list("author", flat=True)
            .distinct()
        )
        context["genres"] = (
            Book.objects.exclude(genre="")
            .order_by("genre")
            .values_list("genre", flat=True)
            .distinct()
        )
        context["years"] = (
            Book.objects.order_by("-publish_year")
            .values_list("publish_year", flat=True)
            .distinct()
        )

        params = self.request.GET.copy()
        if "page" in params:
            del params["page"]
        context["query_params"] = params.urlencode()

        return context


class AdminBookListView(LoginRequiredMixin, ListView):
    """Admin view for managing books - shows full table with edit/delete"""
    model = Book
    template_name = "books/admin_book_list.html"
    context_object_name = "books"
    paginate_by = 15

    def dispatch(self, request, *args, **kwargs):
        # Only admin can access
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'ADMIN'):
            return redirect('books:book_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Book.objects.all()
        search = self.request.GET.get("search", "").strip()
        author = self.request.GET.get("author", "").strip()
        genre = self.request.GET.get("genre", "").strip()

        if search:
            queryset = queryset.filter(title__icontains=search)
        if author:
            queryset = queryset.filter(author__icontains=author)
        if genre:
            queryset = queryset.filter(genre=genre)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context["search"] = self.request.GET.get("search", "").strip()
        context["selected_author"] = self.request.GET.get("author", "").strip()
        context["selected_genre"] = self.request.GET.get("genre", "").strip()

        context["authors"] = (
            Book.objects.exclude(author="")
            .order_by("author")
            .values_list("author", flat=True)
            .distinct()
        )
        context["genres"] = (
            Book.objects.exclude(genre="")
            .order_by("genre")
            .values_list("genre", flat=True)
            .distinct()
        )

        params = self.request.GET.copy()
        if "page" in params:
            del params["page"]
        context["query_params"] = params.urlencode()

        return context


class BookDetailView(DetailView):
    model = Book
    template_name = "books/book_detail.html"
    context_object_name = "book"

    def get_object(self, queryset=None):
        return get_object_or_404(Book, pk=self.kwargs.get("pk"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book = self.get_object()
        
        from reviews.models import Review
        from reviews.views import get_book_average_rating
        
        reviews = Review.objects.filter(book=book).select_related("user")
        context["reviews"] = reviews
        context["average_rating"] = get_book_average_rating(book.id)
        
        if self.request.user.is_authenticated:
            context["user_review"] = reviews.filter(user=self.request.user).first()
        
        return context


class BookCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = "books/book_form.html"
    success_url = reverse_lazy("books:book_list")
    permission_required = "books.add_book"

    def has_permission(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or
            getattr(user, "role", None) == "ADMIN" or
            super().has_permission()
        )

    def form_valid(self, form):
        messages.success(self.request, "Book created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)


class BookUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = "books/book_form.html"
    permission_required = "books.change_book"

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.object.pk})

    def has_permission(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or
            getattr(user, "role", None) == "ADMIN" or
            super().has_permission()
        )

    def form_valid(self, form):
        messages.success(self.request, "Book updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)


class BookDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Book
    template_name = "books/book_confirm_delete.html"
    context_object_name = "book"
    success_url = reverse_lazy("books:book_list")
    permission_required = "books.delete_book"

    def has_permission(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or
            getattr(user, "role", None) == "ADMIN" or
            super().has_permission()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book = self.get_object()
        
        # Calculate average rating
        from reviews.models import Review
        from django.db.models import Avg
        
        avg_rating = Review.objects.filter(book=book).aggregate(avg=Avg('rating'))['avg']
        if avg_rating:
            context['average_rating'] = round(avg_rating, 1)
        else:
            context['average_rating'] = None
            
        return context

    def form_valid(self, form):
        messages.success(self.request, "Book deleted successfully.")
        return super().form_valid(form)
    