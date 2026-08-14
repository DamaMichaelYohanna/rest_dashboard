from django.db import models
from django.utils import timezone
from django.conf import settings
import os

class MoniepointConfig(models.Model):
    ENV_CHOICES = [
        ('SANDBOX', 'Sandbox / Testing'),
        ('PRODUCTION', 'Production / Live'),
    ]

    api_key = models.CharField(max_length=255, blank=True, help_text="Moniepoint POS Authorization API Key")
    business_id = models.CharField(max_length=100, blank=True, help_text="POS Business ID")
    webhook_secret = models.CharField(max_length=255, blank=True, help_text="Webhook Secret Key for Signature Verification")
    environment = models.CharField(max_length=20, choices=ENV_CHOICES, default='SANDBOX')
    is_live_sync_enabled = models.BooleanField(default=True, help_text="Enable real-time background sync & webhook ingestion")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Moniepoint API Configuration"
        verbose_name_plural = "Moniepoint API Configurations"

    def __str__(self):
        return f"Moniepoint Config ({self.environment})"

    @classmethod
    def get_solo(cls):
        """Fetch active configuration dynamically from .env environment variables"""
        api_key = os.getenv('MONIEPOINT_API_KEY') or getattr(settings, 'MONIEPOINT_API_KEY', '')
        business_id = os.getenv('MONIEPOINT_BUSINESS_ID') or getattr(settings, 'MONIEPOINT_BUSINESS_ID', '')
        webhook_secret = os.getenv('MONIEPOINT_WEBHOOK_SECRET') or getattr(settings, 'MONIEPOINT_WEBHOOK_SECRET', '')
        environment = os.getenv('MONIEPOINT_ENVIRONMENT') or getattr(settings, 'MONIEPOINT_ENVIRONMENT', 'SANDBOX')

        obj, created = cls.objects.get_or_create(id=1, defaults={
            'api_key': api_key,
            'business_id': business_id,
            'webhook_secret': webhook_secret,
            'environment': environment
        })

        if not created:
            obj.api_key = api_key
            obj.business_id = business_id
            obj.webhook_secret = webhook_secret
            obj.environment = environment
            obj.save()

        return obj


class Terminal(models.Model):
    STATUS_CHOICES = [
        ('ONLINE', 'Online'),
        ('OFFLINE', 'Offline'),
        ('MAINTENANCE', 'Maintenance'),
    ]

    name = models.CharField(max_length=100, help_text="e.g. Main Bar POS #1")
    serial_number = models.CharField(max_length=100, unique=True, help_text="Moniepoint POS Serial Number")
    location_tag = models.CharField(max_length=100, default="Dining Area", help_text="e.g. Bar, Dining Room, Outdoor Patio, Takeout")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ONLINE')
    is_active = models.BooleanField(default=True)
    last_ping = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

    @property
    def total_today_sales(self):
        today = timezone.now().date()
        sales = self.transactions.filter(
            status='SUCCESS',
            created_at__date=today
        ).aggregate(total=models.Sum('amount'))['total']
        return sales or 0


class Transaction(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Successful'),
        ('FAILED', 'Failed'),
        ('PENDING', 'Pending'),
        ('REVERSED', 'Reversed'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('CARD_PURCHASE', 'Card Payment'),
        ('POS_TRANSFER', 'Bank Transfer'),
        ('USSD', 'USSD'),
        ('PAYCODE', 'PayCode'),
        ('ANY', 'Any / Multi'),
    ]

    TRANSACTION_TYPE_CHOICES = [
        ('PURCHASE', 'POS Purchase'),
        ('POS_TRANSFER', 'Transfer'),
        ('CARD_TRANSFER', 'Card Transfer'),
        ('BILL_PAYMENT', 'Bill Payment'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('BOOM', 'Boom Payment'),
    ]

    merchant_reference = models.CharField(max_length=100, unique=True, db_index=True)
    moniepoint_reference = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    terminal = models.ForeignKey(Terminal, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    terminal_serial = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount in NGN (Naira)")
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='CARD_PURCHASE')
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPE_CHOICES, default='PURCHASE')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    response_code = models.CharField(max_length=10, default='00')
    response_message = models.CharField(max_length=255, default='Approved')
    rrn = models.CharField(max_length=100, blank=True, null=True, verbose_name="RRN")
    card_type = models.CharField(max_length=50, blank=True, help_text="e.g. Mastercard, Visa, Verve, Transfer")
    masked_pan = models.CharField(max_length=30, blank=True, help_text="e.g. 5399****1234")
    customer_name = models.CharField(max_length=150, blank=True, help_text="Customer or Table Note")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.merchant_reference} - ₦{self.amount:,} ({self.status})"


class WebhookLog(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('PENDING', 'Pending'),
    ]

    subscription_event_id = models.CharField(max_length=100, blank=True)
    event_type = models.CharField(max_length=100, default='V1_POS_TRANSACTION')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUCCESS')
    signature_valid = models.BooleanField(default=True)
    headers = models.JSONField(default=dict, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f"{self.event_type} - {self.status} @ {self.received_at.strftime('%H:%M:%S')}"
