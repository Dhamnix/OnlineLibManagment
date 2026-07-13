from django.urls import path
from . import views

app_name = 'notif' 

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='list'),
    path('mark-read/<int:pk>/', views.NotificationMarkReadView.as_view(), name='mark_read'),
    path('mark-all-read/', views.NotificationMarkAllReadView.as_view(), name='mark_all_read'),
    path('delete/<int:pk>/', views.NotificationDeleteView.as_view(), name='delete'),
    path('unread-count/', views.NotificationUnreadCountView.as_view(), name='unread_count'),
]