from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_overview, name='dashboard'),
    path('transactions/', views.transactions_list, name='transactions'),
    path('transactions/export/', views.export_transactions_csv, name='export_transactions'),
    path('terminals/', views.terminals_list, name='terminals'),
    path('settings/', views.settings_view, name='settings'),
    
    # API & Webhook Ingestion Endpoints
    path('api/webhooks/moniepoint/', views.webhook_receiver, name='webhook_receiver'),
    path('api/live-feed/', views.live_feed_api, name='live_feed_api'),
]
