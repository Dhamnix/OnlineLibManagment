from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import BookForm
from .models import Book


class BookListView(ListView):
    model = Book
    template_name = "books/book_list.html"
    context_object_name = "books"
    paginate_by = 10

    def get_queryset(self):
        queryset = Book.objects.all()
        search = self.request.GET.get("search", "").strip()
        author = self.request.GET.get("author", "").strip()
        genre = self.request.GET.get("genre", "").strip()
        year = self.request.GET.get("year", "").strip()

        if search:
            queryset = queryset.filter(title__icontains=search)
        if author:
            queryset = queryset.filter(author=author)
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

        # Fetch options for dropdown filters
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

        # Build querystring parameters for pagination links, keeping current filters intact
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


class BookCreateView(CreateView):
    model = Book
    form_class = BookForm
    template_name = "books/book_form.html"
    success_url = reverse_lazy("books:book_list")

    def form_valid(self, form):
        messages.success(self.request, "Book created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)


class BookUpdateView(UpdateView):
    model = Book
    form_class = BookForm
    template_name = "books/book_form.html"

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Book updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)


class BookDeleteView(DeleteView):
    model = Book
    template_name = "books/book_confirm_delete.html"
    context_object_name = "book"
    success_url = reverse_lazy("books:book_list")

    def form_valid(self, form):
        messages.success(self.request, "Book deleted successfully.")
        return super().form_valid(form)
