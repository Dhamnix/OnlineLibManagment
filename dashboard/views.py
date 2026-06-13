from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView
from django.views import View
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth import get_user_model
import csv

from borrowing.models import Borrow, Reservation, Fine
from books.models import Book
from recommendations.services import recommend_for_user, similar_books

User = get_user_model()


# ========================================
# PUBLIC HOME VIEW
# ========================================

class HomeView(TemplateView):
    """Public landing page for the application."""
    
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Most popular books (by borrow count)
        popular_books = (
            Book.objects.annotate(borrow_count=Count("borrowings"))
            .order_by("-borrow_count", "title")[:5]
        )

        # Latest books (fallback if popularity is low)
        latest_books = Book.objects.order_by("-pk")[:5]

        context["popular_books"] = popular_books
        context["latest_books"] = latest_books

        # Role-based quick links
        user = self.request.user
        context["user"] = user
        if user.is_authenticated:
            context["is_admin"] = user.is_superuser or getattr(user, "role", None) == "ADMIN"
        else:
            context["is_admin"] = False

        return context


# ========================================
# USER DASHBOARD (FOR REGULAR USERS)
# ========================================

class DashboardView(LoginRequiredMixin, TemplateView):
    """User-facing dashboard including recommendation sections."""
    
    template_name = "dashboard/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Active borrowings (not returned)
        active_borrowings = (
            Borrow.objects.filter(user=user, status=Borrow.StatusChoices.BORROWED)
            .select_related("book")
            .order_by("due_date")
        )

        # Reservations (exclude cancelled)
        reservations = (
            Reservation.objects.filter(user=user)
            .exclude(status=Reservation.StatusChoices.CANCELLED)
            .select_related("book")
        )

        # Outstanding fines
        outstanding_fines_qs = (
            Fine.objects.filter(user=user, is_paid=False)
            .select_related("borrow", "borrow__book")
        )
        fines_total = outstanding_fines_qs.aggregate(total=Sum("amount"))["total"] or 0

        # Recommended For You (from recommendation service)
        recommended_for_you = recommend_for_user(user, limit=6)

        # Similar Books: base on user's most recently borrowed book
        last_borrow = (
            Borrow.objects.filter(user=user)
            .select_related("book")
            .order_by("-borrow_date")
            .first()
        )
        similar_books_list = []
        if last_borrow and last_borrow.book:
            similar_books_list = similar_books(last_borrow.book, limit=6)

        context.update(
            {
                "active_borrowings": active_borrowings,
                "reservations": reservations,
                "outstanding_fines": outstanding_fines_qs,
                "fines_total": fines_total,
                "recommended_for_you": recommended_for_you,
                "similar_books": similar_books_list,
            }
        )
        return context


# ========================================
# ADMIN DASHBOARD
# ========================================

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Admin dashboard showing aggregates and popular items."""
    
    template_name = "dashboard/admin_dashboard.html"

    def test_func(self):
        # Only staff users, superusers, or ADMINS can access
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Total books
        total_books = Book.objects.count()

        # Total users
        total_users = User.objects.count()

        # Active borrowings (status BORROWED)
        active_borrowings_qs = Borrow.objects.filter(
            status=Borrow.StatusChoices.BORROWED
        ).select_related("user", "book")
        active_borrowings = active_borrowings_qs.count()

        # Overdue borrowings: borrowed and due_date in the past
        now = timezone.now()
        overdue_qs = active_borrowings_qs.filter(due_date__lt=now).order_by("due_date")
        overdue_count = overdue_qs.count()

        # Most popular books by borrow count
        popular_books = (
            Book.objects.annotate(borrow_count=Count("borrowings"))
            .order_by("-borrow_count", "title")[:10]
            .select_related()
        )

        # Recent users (last 5)
        recent_users = User.objects.order_by("-date_joined")[:5]

        context.update(
            {
                "total_books": total_books,
                "total_users": total_users,
                "active_borrowings_count": active_borrowings,
                "overdue_count": overdue_count,
                "overdue_list": overdue_qs,
                "popular_books": popular_books,
                "recent_users": recent_users,
            }
        )
        return context


# ========================================
# ADMIN USER MANAGEMENT
# ========================================

class AdminUsersView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Admin view for managing all users"""
    
    template_name = "dashboard/admin_users.html"
    model = User
    context_object_name = "users"
    paginate_by = 15

    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get_queryset(self):
        queryset = User.objects.annotate(
            borrowings_count=Count('borrowings', filter=Q(borrowings__status='BORROWED')),
            fines_total=Sum('fines__amount', filter=Q(fines__is_paid=False)),
            fines_unpaid_count=Count('fines', filter=Q(fines__is_paid=False))
        )
        
        # Search filter
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        
        # Role filter
        role = self.request.GET.get('role', '')
        if role:
            queryset = queryset.filter(role=role)
        
        # Status filter
        status = self.request.GET.get('status', '')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('-date_joined')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['role_filter'] = self.request.GET.get('role', '')
        context['status_filter'] = self.request.GET.get('status', '')
        return context


class AdminUserAddView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Add a new user from admin panel"""
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def post(self, request):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        role = request.POST.get('role', 'MEMBER')

        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
            return redirect('dashboard:admin_users')
        
        # Check if email exists
        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists.')
            return redirect('dashboard:admin_users')

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        
        messages.success(request, f'User "{username}" created successfully.')
        return redirect('dashboard:admin_users')


class AdminUserDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Delete a user from admin panel"""
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def post(self, request, pk):
        user_to_delete = get_object_or_404(User, pk=pk)
        
        # Prevent deleting yourself
        if user_to_delete == request.user:
            messages.error(request, 'You cannot delete your own account.')
            return redirect('dashboard:admin_users')
        
        username = user_to_delete.username
        user_to_delete.delete()
        messages.success(request, f'User "{username}" deleted successfully.')
        return redirect('dashboard:admin_users')


class AdminUserExportView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Export all users to CSV file"""
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get(self, request):
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
        
        # Create CSV writer
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'ID', 'Username', 'Email', 'First Name', 'Last Name', 
            'Role', 'Active', 'Staff', 'Superuser', 'Date Joined', 'Last Login'
        ])
        
        # Write data
        users = User.objects.all().order_by('-date_joined')
        for user in users:
            writer.writerow([
                user.id, 
                user.username, 
                user.email, 
                user.first_name, 
                user.last_name,
                user.role,
                user.is_active,
                user.is_staff,
                user.is_superuser,
                user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
                user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else ''
            ])
        
        return response


class AdminUserViewDetail(LoginRequiredMixin, UserPassesTestMixin, View):
    """View user details (AJAX for modal)"""
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        
        # Get user statistics
        active_borrowings = Borrow.objects.filter(
            user=user, 
            status=Borrow.StatusChoices.BORROWED
        ).count()
        
        total_borrowings = Borrow.objects.filter(user=user).count()
        
        unpaid_fines = Fine.objects.filter(user=user, is_paid=False)
        fines_total = unpaid_fines.aggregate(total=Sum('amount'))['total'] or 0
        
        active_reservations = Reservation.objects.filter(
            user=user,
            status__in=[Reservation.StatusChoices.PENDING, Reservation.StatusChoices.AVAILABLE]
        ).count()
        
        html = f"""
        <div class="user-detail-modal">
            <div class="d-flex align-items-center gap-3 mb-4">
                <div class="user-avatar-large">
                    {user.username|first|upper}
                </div>
                <div>
                    <h6 class="mb-0">{user.get_full_name|default:user.username}</h6>
                    <small class="text-muted">@{user.username}</small>
                </div>
            </div>
            
            <div class="row g-3 mb-4">
                <div class="col-6">
                    <div class="info-box">
                        <div class="small text-muted">Email</div>
                        <div class="fw-semibold">{user.email}</div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="info-box">
                        <div class="small text-muted">Role</div>
                        <div class="fw-semibold">{user.get_role_display()}</div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="info-box">
                        <div class="small text-muted">Joined</div>
                        <div class="fw-semibold">{user.date_joined.strftime('%B %d, %Y')}</div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="info-box">
                        <div class="small text-muted">Status</div>
                        <div class="fw-semibold text-{'success' if user.is_active else 'danger'}">
                            {'Active' if user.is_active else 'Inactive'}
                        </div>
                    </div>
                </div>
            </div>
            
            <h6 class="fw-bold mb-3">Library Statistics</h6>
            <div class="row g-3">
                <div class="col-4">
                    <div class="stat-box text-center">
                        <div class="stat-number">{active_borrowings}</div>
                        <div class="stat-label-sm">Active Borrowings</div>
                    </div>
                </div>
                <div class="col-4">
                    <div class="stat-box text-center">
                        <div class="stat-number">{total_borrowings}</div>
                        <div class="stat-label-sm">Total Borrowings</div>
                    </div>
                </div>
                <div class="col-4">
                    <div class="stat-box text-center">
                        <div class="stat-number text-{'danger' if fines_total > 0 else 'success'}">
                            ${fines_total}
                        </div>
                        <div class="stat-label-sm">Unpaid Fines</div>
                    </div>
                </div>
            </div>
        </div>
        
        <style>
            .user-avatar-large {{
                width: 60px;
                height: 60px;
                background: linear-gradient(135deg, #6366f1, #10b981);
                border-radius: 50px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 1.5rem;
                font-weight: 700;
            }}
            .info-box {{
                background: #f8fafc;
                padding: 0.75rem;
                border-radius: 12px;
            }}
            .stat-box {{
                background: #f8fafc;
                padding: 0.75rem;
                border-radius: 12px;
            }}
            .stat-number {{
                font-size: 1.2rem;
                font-weight: 700;
                color: #0f172a;
            }}
            .stat-label-sm {{
                font-size: 0.7rem;
                color: #64748b;
            }}
        </style>
        """
        
        return HttpResponse(html)


class AdminUserEditView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Edit user form (AJAX for modal)"""
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        
        html = f"""
        <form method="post" action="/dashboard/admin/users/{user.id}/update/">
            <input type="hidden" name="csrfmiddlewaretoken" value="{request.COOKIES.get('csrftoken', '')}">
            
            <div class="mb-3">
                <label class="form-label">Username</label>
                <input type="text" name="username" class="form-control" value="{user.username}" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Email</label>
                <input type="email" name="email" class="form-control" value="{user.email}" required>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">First Name</label>
                    <input type="text" name="first_name" class="form-control" value="{user.first_name}">
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Last Name</label>
                    <input type="text" name="last_name" class="form-control" value="{user.last_name}">
                </div>
            </div>
            <div class="mb-3">
                <label class="form-label">Role</label>
                <select name="role" class="form-select">
                    <option value="MEMBER" {'selected' if user.role == 'MEMBER' else ''}>Member</option>
                    <option value="ADMIN" {'selected' if user.role == 'ADMIN' else ''}>Admin</option>
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label">Status</label>
                <select name="is_active" class="form-select">
                    <option value="true" {'selected' if user.is_active else ''}>Active</option>
                    <option value="false" {'selected' if not user.is_active else ''}>Inactive</option>
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label">New Password (leave blank to keep current)</label>
                <input type="password" name="password" class="form-control" placeholder="Enter new password...">
            </div>
            <div class="modal-footer px-0 pb-0">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="submit" class="btn btn-primary">Save Changes</button>
            </div>
        </form>
        """
        
        return HttpResponse(html)


class AdminUserUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Update user information"""
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        role = request.POST.get('role')
        is_active = request.POST.get('is_active') == 'true'
        password = request.POST.get('password', '')
        
        # Check username uniqueness
        if User.objects.exclude(pk=pk).filter(username=username).exists():
            messages.error(request, f'Username "{username}" already taken.')
            return redirect('dashboard:admin_users')
        
        # Check email uniqueness
        if User.objects.exclude(pk=pk).filter(email=email).exists():
            messages.error(request, f'Email "{email}" already taken.')
            return redirect('dashboard:admin_users')
        
        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.role = role
        user.is_active = is_active
        
        if password:
            user.set_password(password)
        
        user.save()
        
        messages.success(request, f'User "{username}" updated successfully.')
        return redirect('dashboard:admin_users')
    
class AdminUserDataView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Get user data as JSON for edit form"""
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_active': user.is_active,
            'date_joined': user.date_joined.strftime('%Y-%m-%d'),
        }
        return JsonResponse(data)