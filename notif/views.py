# notif/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.views import View
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 15

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(user=user)
        
        type_filter = self.request.GET.get('type', '')
        if type_filter:
            queryset = queryset.filter(type=type_filter)
        
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'unread':
            queryset = queryset.filter(is_read=False)
        elif status_filter == 'read':
            queryset = queryset.filter(is_read=True)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context['unread_count'] = Notification.objects.filter(user=user, is_read=False).count()
        context['total_count'] = Notification.objects.filter(user=user).count()
        context['current_type'] = self.request.GET.get('type', '')
        context['current_status'] = self.request.GET.get('status', '')
        
        return context


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notification.mark_as_read()
        
        # اگر درخواست AJAX باشد، JSON برمی‌گرداند
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Notification marked as read',
                'unread_count': Notification.objects.filter(user=request.user, is_read=False).count()
            })
        
        if notification.link:
            return redirect(notification.link)
        
        return redirect('notif:list')


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        # اگر درخواست AJAX باشد، JSON برمی‌گرداند
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'{count} notification(s) marked as read',
                'unread_count': 0
            })
        
        messages.success(request, f"{count} notification(s) marked as read.")
        return redirect('notif:list')


class NotificationDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notification.delete()
        

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Notification deleted successfully',
                'unread_count': Notification.objects.filter(user=request.user, is_read=False).count()
            })
        
        messages.success(request, "Notification deleted successfully.")
        return redirect('notif:list')


class NotificationUnreadCountView(LoginRequiredMixin, View):
    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return JsonResponse({'unread_count': count})