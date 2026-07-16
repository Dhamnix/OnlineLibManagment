from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Sum, Q, Avg
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, UpdateView
from django.contrib.auth.forms import PasswordChangeForm

from .forms import BootstrapAuthenticationForm, CustomUserRegistrationForm
from borrowing.models import Borrow, Reservation, Fine
from .models import CustomUser
from books.models import Book
from reviews.models import Review


class RegisterView(CreateView):
    template_name = "registration/register.html"
    form_class = CustomUserRegistrationForm
    success_url = reverse_lazy("accounts:profile")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:profile")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        role = self.request.POST.get("role")
        if role in [CustomUser.Role.ADMIN, CustomUser.Role.MEMBER]:
            self.object.role = role
        self.object.save()
        login(self.request, self.object)
        messages.success(self.request, "Your account has been created successfully.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)


class CustomLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = BootstrapAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("accounts:profile")

    def form_valid(self, form):
        messages.success(self.request, "You are now logged in.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password.", extra_tags="danger")
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "You have been logged out.")
        return response


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"
    login_url = reverse_lazy("accounts:login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Total books borrowed (all time)
        context['total_borrowed'] = Borrow.objects.filter(user=user).count()
        
        # Currently active borrowings (not returned yet)
        context['active_borrowings'] = Borrow.objects.filter(
            user=user, 
            status=Borrow.StatusChoices.BORROWED
        ).count()
        
        # Active reservations (not cancelled/completed)
        context['active_reservations'] = Reservation.objects.filter(
            user=user
        ).exclude(
            status__in=[
                Reservation.StatusChoices.CANCELLED,
                Reservation.StatusChoices.COMPLETED
            ]
        ).count()
        
        # Total unpaid fines amount
        total_fines = Fine.objects.filter(
            user=user, 
            is_paid=False
        ).aggregate(total=Sum('amount'))['total']
        context['total_fines'] = total_fines or 0
        
        # Recent activity (last 5 borrowings with book info)
        context['recent_borrowings'] = Borrow.objects.filter(
            user=user
        ).select_related('book').order_by('-borrow_date')[:5]

        # ============================================
        # 🎯 PERSONALIZED RECOMMENDATIONS FOR PROFILE
        # ============================================
        
        # 1. Get user's top genres from borrow history
        borrowed_book_ids = Borrow.objects.filter(user=user).values_list('book_id', flat=True)
        user_top_genres = []
        if borrowed_book_ids:
            genres = (
                Book.objects.filter(pk__in=borrowed_book_ids)
                .values('genre')
                .annotate(count=Count('id'))
                .order_by('-count')[:3]
            )
            user_top_genres = [g['genre'] for g in genres]
        
        # 2. Get user's highly rated books (rating >= 4)
        highly_rated_book_ids = Review.objects.filter(
            user=user, 
            rating__gte=4
        ).values_list('book_id', flat=True)
        
        # 3. Get user's borrowed book IDs
        user_borrowed_ids = list(borrowed_book_ids)
        
        # 4. Get user's viewed books (from recent borrowings and reviews)
        viewed_book_ids = list(set(
            list(borrowed_book_ids) + 
            list(Review.objects.filter(user=user).values_list('book_id', flat=True))
        ))
        
        # ============================================
        # RECOMMENDATION: Based on Top Genres
        # ============================================
        recommended_by_genre = []
        if user_top_genres:
            recommended_by_genre = (
                Book.objects.filter(genre__in=user_top_genres)
                .exclude(pk__in=user_borrowed_ids)
                .annotate(
                    avg_rating=Avg('reviews__rating'),
                    borrow_count=Count('borrowings')
                )
                .filter(available_copies__gt=0)
                .order_by('-avg_rating', '-borrow_count')[:4]
            )
        
        # ============================================
        # RECOMMENDATION: Based on Highly Rated Books (Similar Genres)
        # ============================================
        recommended_similar_to_rated = []
        if highly_rated_book_ids:
            rated_genres = Book.objects.filter(
                pk__in=highly_rated_book_ids
            ).values_list('genre', flat=True).distinct()
            
            recommended_similar_to_rated = (
                Book.objects.filter(genre__in=rated_genres)
                .exclude(pk__in=list(highly_rated_book_ids) + user_borrowed_ids)
                .annotate(
                    avg_rating=Avg('reviews__rating'),
                    borrow_count=Count('borrowings')
                )
                .filter(available_copies__gt=0)
                .order_by('-avg_rating', '-borrow_count')[:4]
            )
        
        # ============================================
        # RECOMMENDATION: Based on Borrow History (Co-borrowed)
        # ============================================
        recommended_co_borrowed = []
        if user_borrowed_ids:
            other_user_ids = (
                Borrow.objects.filter(book_id__in=user_borrowed_ids)
                .exclude(user=user)
                .values_list('user_id', flat=True)
                .distinct()
            )
            
            if other_user_ids:
                recommended_co_borrowed = (
                    Book.objects.filter(
                        borrowings__user_id__in=other_user_ids
                    )
                    .exclude(pk__in=user_borrowed_ids)
                    .annotate(
                        shared_count=Count('borrowings'),
                        avg_rating=Avg('reviews__rating')
                    )
                    .filter(available_copies__gt=0)
                    .order_by('-shared_count', '-avg_rating')[:4]
                )
        
        # ============================================
        # RECOMMENDATION: Trending/Popular Books (Fallback)
        # ============================================
        trending_books = (
            Book.objects.annotate(
                borrow_count=Count('borrowings'),
                avg_rating=Avg('reviews__rating')
            )
            .filter(available_copies__gt=0)
            .exclude(pk__in=viewed_book_ids)
            .order_by('-borrow_count', '-avg_rating')[:4]
        )
        
        # ============================================
        # MERGE ALL RECOMMENDATIONS (Remove duplicates)
        # ============================================
        all_recommendations = []
        seen_ids = set()
        
        for book in recommended_by_genre:
            if book.id not in seen_ids:
                all_recommendations.append(book)
                seen_ids.add(book.id)
        
        for book in recommended_similar_to_rated:
            if book.id not in seen_ids:
                all_recommendations.append(book)
                seen_ids.add(book.id)
        
        for book in recommended_co_borrowed:
            if book.id not in seen_ids:
                all_recommendations.append(book)
                seen_ids.add(book.id)
        
        for book in trending_books:
            if book.id not in seen_ids:
                all_recommendations.append(book)
                seen_ids.add(book.id)
                if len(all_recommendations) >= 12:
                    break
        
        # ============================================
        # STATISTICS FOR PROFILE
        # ============================================
        
        most_borrowed_genre = None
        if user_top_genres:
            most_borrowed_genre = user_top_genres[0] if user_top_genres else None
        
        user_avg_rating = Review.objects.filter(user=user).aggregate(avg=Avg('rating'))['avg']
        total_reviews = Review.objects.filter(user=user).count()
        favorite_genre = most_borrowed_genre
        currently_borrowed = Borrow.objects.filter(
            user=user,
            status=Borrow.StatusChoices.BORROWED
        ).count()
        
        context.update({
            'user_top_genres': user_top_genres,
            'favorite_genre': favorite_genre,
            'user_avg_rating': user_avg_rating or 0,
            'total_reviews': total_reviews,
            'currently_borrowed': currently_borrowed,
            'recommended_books': all_recommendations[:12],
            'recommended_by_genre': recommended_by_genre[:4],
            'recommended_similar_to_rated': recommended_similar_to_rated[:4],
            'recommended_co_borrowed': recommended_co_borrowed[:4],
            'trending_books': trending_books[:4],
        })
        
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    fields = ['first_name', 'last_name', 'email']
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Your profile has been updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)


class ChangePasswordView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = PasswordChangeForm
    template_name = "accounts/change_password.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        user = form.save()
        update_session_auth_hash(self.request, user)
        messages.success(self.request, "Your password has been changed successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)