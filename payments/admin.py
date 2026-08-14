from django.contrib import admin
from .models import MoniepointConfig, Terminal, Transaction, WebhookLog

@admin.register(MoniepointConfig)
class MoniepointConfigAdmin(admin.ModelAdmin):
    list_display = ('environment', 'business_id', 'is_live_sync_enabled', 'updated_at')

@admin.register(Terminal)
class TerminalAdmin(admin.ModelAdmin):
    list_display = ('name', 'serial_number', 'location_tag', 'status', 'is_active', 'last_ping')
    list_filter = ('status', 'location_tag', 'is_active')
    search_fields = ('name', 'serial_number', 'location_tag')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('merchant_reference', 'amount', 'status', 'payment_method', 'terminal', 'customer_name', 'created_at')
    list_filter = ('status', 'payment_method', 'transaction_type', 'created_at')
    search_fields = ('merchant_reference', 'moniepoint_reference', 'rrn', 'customer_name', 'terminal_serial')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'status', 'signature_valid', 'subscription_event_id', 'received_at')
    list_filter = ('status', 'signature_valid', 'event_type')
    search_fields = ('subscription_event_id', 'event_type')
    readonly_fields = ('received_at',)
