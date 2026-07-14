from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, DetailView
from django.views import View
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import get_user_model
import csv

from borrowing.models import Borrow, Reservation, Fine
from books.models import Book
from recommendations.services import recommend_for_user, similar_books

User = get_user_model()


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        popular_books = (
            Book.objects.annotate(borrow_count=Count("borrowings"))
            .order_by("-borrow_count", "title")[:5]
        )
        context["popular_books"] = popular_books
        user = self.request.user
        context["user"] = user
        if user.is_authenticated:
            context["is_admin"] = user.is_superuser or getattr(user, "role", None) == "ADMIN"
        else:
            context["is_admin"] = False
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        active_borrowings = (
            Borrow.objects.filter(user=user, status=Borrow.StatusChoices.BORROWED)
            .select_related("book")
            .order_by("due_date")
        )

        reservations = (
            Reservation.objects.filter(user=user)
            .exclude(status=Reservation.StatusChoices.CANCELLED)
            .select_related("book")
        )

        outstanding_fines_qs = (
            Fine.objects.filter(user=user, is_paid=False)
            .select_related("borrow", "borrow__book")
        )
        fines_total = outstanding_fines_qs.aggregate(total=Sum("amount"))["total"] or 0

        recommended_for_you = recommend_for_user(user, limit=6)

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


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "dashboard/admin_dashboard.html"

    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        total_books = Book.objects.count()
        total_users = User.objects.count()

        active_borrowings_qs = Borrow.objects.filter(
            status=Borrow.StatusChoices.BORROWED
        ).select_related("user", "book")
        active_borrowings = active_borrowings_qs.count()

        now = timezone.now()
        overdue_qs = active_borrowings_qs.filter(due_date__lt=now).order_by("due_date")
        overdue_count = overdue_qs.count()

        # Pending borrow requests
        pending_requests_qs = Borrow.objects.filter(
            status=Borrow.StatusChoices.PENDING
        ).select_related("user", "book").order_by("request_date")
        pending_requests_count = pending_requests_qs.count()

        popular_books = (
            Book.objects.annotate(borrow_count=Count("borrowings"))
            .order_by("-borrow_count", "title")[:10]
        )

        recent_users = User.objects.order_by("-date_joined")[:5]

        context.update(
            {
                "total_books": total_books,
                "total_users": total_users,
                "active_borrowings_count": active_borrowings,
                "overdue_count": overdue_count,
                "overdue_list": overdue_qs,
                "pending_requests_count": pending_requests_count,
                "pending_requests": pending_requests_qs[:5],
                "popular_books": popular_books,
                "recent_users": recent_users,
            }
        )
        return context


class AdminUsersView(LoginRequiredMixin, UserPassesTestMixin, ListView):
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
        )
        
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        
        role = self.request.GET.get('role', '')
        if role:
            queryset = queryset.filter(role=role)
        
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
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get(self, request):
        return render(request, 'dashboard/admin_user_form.html', {'is_add': True})


class AdminUserCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def post(self, request):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        role = request.POST.get('role', 'MEMBER')

        # بررسی تطابق رمز عبور
        if password != password2:
            messages.error(request, 'Passwords do not match!')
            return redirect('dashboard:admin_user_add')

        # بررسی وجود کاربر
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
            return redirect('dashboard:admin_user_add')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists.')
            return redirect('dashboard:admin_user_add')

        # ایجاد کاربر جدید
        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        
        messages.success(request, f'User "{username}" created successfully.')
        return redirect('dashboard:admin_users')


class AdminUserEditView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        return render(request, 'dashboard/admin_user_form.html', {'user': user, 'is_add': False})


class AdminUserUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
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
        password = request.POST.get('password', '')
        is_active = request.POST.get('is_active') == 'true' if request.POST.get('is_active') else user.is_active
        
        # بررسی تکراری بودن username
        if User.objects.exclude(pk=pk).filter(username=username).exists():
            messages.error(request, f'Username "{username}" already taken.')
            return redirect('dashboard:admin_user_edit', pk=pk)
        
        # بررسی تکراری بودن email
        if User.objects.exclude(pk=pk).filter(email=email).exists():
            messages.error(request, f'Email "{email}" already taken.')
            return redirect('dashboard:admin_user_edit', pk=pk)
        
        # به‌روزرسانی اطلاعات
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


class AdminUserDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def post(self, request, pk):
        user_to_delete = get_object_or_404(User, pk=pk)
        
        if user_to_delete == request.user:
            messages.error(request, 'You cannot delete your own account.')
            return redirect('dashboard:admin_users')
        
        username = user_to_delete.username
        user_to_delete.delete()
        
        messages.success(request, f'User "{username}" deleted successfully.')
        return redirect('dashboard:admin_users')


class AdminUserExportView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Username', 'Email', 'First Name', 'Last Name', 
            'Role', 'Active', 'Staff', 'Superuser', 'Date Joined', 'Last Login'
        ])
        
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


class AdminUserProfileView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = User
    template_name = 'dashboard/admin_user_profile.html'
    context_object_name = 'profile_user'
    pk_url_kwarg = 'pk'

    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        
        context['active_borrowings'] = Borrow.objects.filter(
            user=user, 
            status=Borrow.StatusChoices.BORROWED
        ).count()
        
        context['total_borrowings'] = Borrow.objects.filter(user=user).count()
        
        unpaid_fines = Fine.objects.filter(user=user, is_paid=False)
        context['fines_total'] = unpaid_fines.aggregate(total=Sum('amount'))['total'] or 0
        
        context['active_reservations'] = Reservation.objects.filter(
            user=user,
            status__in=[Reservation.StatusChoices.PENDING, Reservation.StatusChoices.AVAILABLE]
        ).count()
        
        context['recent_borrowings'] = Borrow.objects.filter(user=user).select_related('book').order_by('-borrow_date')[:10]
        
        context['fines'] = Fine.objects.filter(user=user).select_related('borrow', 'borrow__book').order_by('-borrow__borrow_date')
        
        colors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4']
        color_index = sum(ord(c) for c in user.username) % len(colors)
        context['avatar_color'] = colors[color_index]
        
        initials = ''
        if user.first_name:
            initials += user.first_name[0].upper()
        if user.last_name:
            initials += user.last_name[0].upper()
        if not initials:
            initials = user.username[0].upper()
        context['initials'] = initials
        
        context['now'] = timezone.now()
        
        return context


class AdminUserViewDetail(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "ADMIN"

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        
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
        
        recent_borrowings = Borrow.objects.filter(user=user).select_related('book').order_by('-borrow_date')[:5]
        
        colors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4']
        color_index = sum(ord(c) for c in user.username) % len(colors)
        avatar_color = colors[color_index]
        
        initials = ''
        if user.first_name:
            initials += user.first_name[0].upper()
        if user.last_name:
            initials += user.last_name[0].upper()
        if not initials:
            initials = user.username[0].upper()
        
        recent_html = ''
        if recent_borrowings:
            for borrow in recent_borrowings:
                status_badge = 'bg-success' if borrow.status == 'RETURNED' else 'bg-warning'
                status_text = 'Returned' if borrow.status == 'RETURNED' else 'Borrowed'
                recent_html += f'''
                    <div class="activity-item">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <div class="fw-semibold">{borrow.book.title}</div>
                                <div class="small text-muted">{borrow.book.author}</div>
                            </div>
                            <span class="badge {status_badge}">{status_text}</span>
                        </div>
                        <div class="small text-muted mt-1">
                            <i class="fas fa-calendar-alt me-1"></i>
                            {borrow.borrow_date.strftime('%b %d, %Y')}
                        </div>
                    </div>
                '''
        else:
            recent_html = '<div class="text-muted text-center py-3">No borrowing history</div>'
        
        status_class = 'success' if user.is_active else 'danger'
        status_text = 'Active' if user.is_active else 'Inactive'
        fines_class = 'danger' if fines_total > 0 else 'success'
        role_icon = 'crown' if user.role == 'ADMIN' else 'user'
        
        html = f"""
        <div class="user-profile-modal">
            <div class="profile-header-card" style="background: linear-gradient(135deg, {avatar_color}, {avatar_color}dd);">
                <div class="row align-items-center">
                    <div class="col-auto">
                        <div class="profile-avatar-lg" style="background: rgba(255,255,255,0.2);">
                            {initials}
                        </div>
                    </div>
                    <div class="col">
                        <h4 class="text-white mb-1">{user.get_full_name() or user.username}</h4>
                        <div class="d-flex flex-wrap gap-2 align-items-center">
                            <span class="badge bg-white text-dark">
                                <i class="fas fa-user me-1"></i> @{user.username}
                            </span>
                            <span class="badge bg-white text-dark">
                                <i class="fas fa-envelope me-1"></i> {user.email}
                            </span>
                            <span class="badge bg-white text-{status_class}">
                                <i class="fas fa-circle me-1"></i>
                                {status_text}
                            </span>
                        </div>
                        <div class="mt-2">
                            <span class="badge bg-light text-dark">
                                <i class="fas fa-{role_icon} me-1"></i>
                                {user.get_role_display()}
                            </span>
                            <span class="badge bg-light text-dark ms-1">
                                <i class="fas fa-calendar-alt me-1"></i>
                                Joined {user.date_joined.strftime('%B %d, %Y')}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row g-3 p-4">
                <div class="col-6 col-md-3">
                    <div class="stat-card-profile">
                        <div class="stat-icon-profile" style="background: rgba(99,102,241,0.1); color: #6366f1;">
                            <i class="fas fa-hand-holding-heart"></i>
                        </div>
                        <div class="stat-number-profile">{active_borrowings}</div>
                        <div class="stat-label-profile">Active Loans</div>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="stat-card-profile">
                        <div class="stat-icon-profile" style="background: rgba(16,185,129,0.1); color: #10b981;">
                            <i class="fas fa-book-open"></i>
                        </div>
                        <div class="stat-number-profile">{total_borrowings}</div>
                        <div class="stat-label-profile">Total Borrowed</div>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="stat-card-profile">
                        <div class="stat-icon-profile" style="background: rgba(245,158,11,0.1); color: #f59e0b;">
                            <i class="fas fa-clock"></i>
                        </div>
                        <div class="stat-number-profile">{active_reservations}</div>
                        <div class="stat-label-profile">Reservations</div>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="stat-card-profile">
                        <div class="stat-icon-profile" style="background: rgba(239,68,68,0.1); color: {'#ef4444' if fines_total > 0 else '#10b981'};">
                            <i class="fas fa-coins"></i>
                        </div>
                        <div class="stat-number-profile text-{fines_class}">
                            ${fines_total}
                        </div>
                        <div class="stat-label-profile">Unpaid Fines</div>
                    </div>
                </div>
            </div>
            
            <div class="px-4 pb-4">
                <h6 class="fw-bold mb-3">
                    <i class="fas fa-history me-2" style="color: #6366f1;"></i>
                    Recent Activity
                </h6>
                <div class="activity-timeline">
                    {recent_html}
                </div>
            </div>
        </div>
        
        <style>
            .profile-header-card {{
                padding: 2rem;
                border-radius: 20px 20px 0 0;
                color: white;
            }}
            .profile-avatar-lg {{
                width: 80px;
                height: 80px;
                border-radius: 50px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 2rem;
                font-weight: 700;
                color: white;
                border: 3px solid rgba(255,255,255,0.3);
            }}
            .stat-card-profile {{
                background: #f8fafc;
                border-radius: 16px;
                padding: 1rem;
                text-align: center;
                transition: all 0.3s ease;
            }}
            .stat-card-profile:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }}
            .stat-icon-profile {{
                width: 45px;
                height: 45px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 0.5rem;
                font-size: 1.2rem;
            }}
            .stat-number-profile {{
                font-size: 1.5rem;
                font-weight: 700;
                color: #0f172a;
            }}
            .stat-label-profile {{
                font-size: 0.65rem;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .activity-timeline {{
                max-height: 200px;
                overflow-y: auto;
            }}
            .activity-timeline::-webkit-scrollbar {{
                width: 4px;
            }}
            .activity-timeline::-webkit-scrollbar-thumb {{
                background: #6366f1;
                border-radius: 10px;
            }}
            .activity-timeline::-webkit-scrollbar-track {{
                background: #f1f5f9;
                border-radius: 10px;
            }}
            .activity-item {{
                padding: 0.75rem 0;
                border-bottom: 1px solid #e2e8f0;
            }}
            .activity-item:last-child {{
                border-bottom: none;
            }}
            .activity-item:hover {{
                background: #f8fafc;
                margin: 0 -0.5rem;
                padding-left: 0.5rem;
                padding-right: 0.5rem;
                border-radius: 8px;
            }}
            .text-success {{
                color: #10b981 !important;
            }}
            .text-danger {{
                color: #ef4444 !important;
            }}
        </style>
        """
        
        return HttpResponse(html)