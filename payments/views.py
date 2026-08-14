import csv
import json
import os
import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg
from django.core.paginator import Paginator
from django.conf import settings

from .models import MoniepointConfig, Terminal, Transaction, WebhookLog
from .services import MoniepointService

def update_env_file(key, value):
    """Helper to update .env file dynamically when user updates credentials"""
    env_path = settings.BASE_DIR / '.env'
    lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    
    if not found:
        new_lines.append(f"{key}={value}\n")

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    os.environ[key] = str(value)

def dashboard_overview(request):
    """Main Restaurant Money Monitoring Dashboard"""
    now = timezone.now()
    today = now.date()
    yesterday = today - timezone.timedelta(days=1)

    # Today Metrics
    today_txns = Transaction.objects.filter(created_at__date=today)
    today_success_txns = today_txns.filter(status='SUCCESS')
    
    today_revenue = today_success_txns.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    today_count = today_txns.count()
    today_success_count = today_success_txns.count()
    
    success_rate = (today_success_count / today_count * 100) if today_count > 0 else 100.0
    avg_ticket = today_revenue / today_success_count if today_success_count > 0 else Decimal('0.00')

    # Yesterday Metrics for Comparison
    yesterday_revenue = Transaction.objects.filter(
        created_at__date=yesterday, status='SUCCESS'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    if yesterday_revenue > 0:
        revenue_growth = ((today_revenue - yesterday_revenue) / yesterday_revenue) * 100
    else:
        revenue_growth = 100.0 if today_revenue > 0 else 0.0

    # Terminal Status
    active_terminals = Terminal.objects.filter(is_active=True, status='ONLINE').count()
    total_terminals = Terminal.objects.filter(is_active=True).count()

    # Chart 1: Hourly Sales Trend Today (24 hours)
    hourly_labels = []
    hourly_data = []
    for h in range(24):
        hourly_labels.append(f"{h:02d}:00")
        h_total = today_success_txns.filter(created_at__hour=h).aggregate(total=Sum('amount'))['total'] or 0
        hourly_data.append(float(h_total))

    # Chart 2: Payment Method Distribution
    card_sales = float(today_success_txns.filter(payment_method='CARD_PURCHASE').aggregate(total=Sum('amount'))['total'] or 0)
    transfer_sales = float(today_success_txns.filter(payment_method='POS_TRANSFER').aggregate(total=Sum('amount'))['total'] or 0)
    other_sales = float(today_success_txns.exclude(payment_method__in=['CARD_PURCHASE', 'POS_TRANSFER']).aggregate(total=Sum('amount'))['total'] or 0)

    # Chart 3: Terminal Sales Breakdown
    terminal_sales_labels = []
    terminal_sales_data = []
    terminals = Terminal.objects.filter(is_active=True)
    for term in terminals:
        terminal_sales_labels.append(term.name)
        terminal_sales_data.append(float(term.total_today_sales))

    # Recent Live Feed
    recent_transactions = Transaction.objects.all()[:12]

    context = {
        'today_revenue': today_revenue,
        'revenue_growth': round(revenue_growth, 1),
        'today_count': today_count,
        'today_success_count': today_success_count,
        'success_rate': round(success_rate, 1),
        'avg_ticket': avg_ticket,
        'active_terminals': active_terminals,
        'total_terminals': total_terminals,
        'hourly_labels_json': json.dumps(hourly_labels),
        'hourly_data_json': json.dumps(hourly_data),
        'method_data_json': json.dumps([card_sales, transfer_sales, other_sales]),
        'terminal_labels_json': json.dumps(terminal_sales_labels),
        'terminal_data_json': json.dumps(terminal_sales_data),
        'recent_transactions': recent_transactions,
        'terminals': terminals,
        'config': MoniepointConfig.get_solo(),
    }
    return render(request, 'payments/dashboard.html', context)


def transactions_list(request):
    """Filterable & Searchable Transactions Table"""
    queryset = Transaction.objects.all()

    # Search filter
    search = request.GET.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(merchant_reference__icontains=search) |
            Q(moniepoint_reference__icontains=search) |
            Q(rrn__icontains=search) |
            Q(customer_name__icontains=search) |
            Q(terminal_serial__icontains=search)
        )

    # Status filter
    status = request.GET.get('status', '').strip()
    if status:
        queryset = queryset.filter(status=status)

    # Payment Method filter
    method = request.GET.get('payment_method', '').strip()
    if method:
        queryset = queryset.filter(payment_method=method)

    # Terminal filter
    terminal_id = request.GET.get('terminal', '').strip()
    if terminal_id:
        queryset = queryset.filter(terminal_id=terminal_id)

    # Date filter
    date_filter = request.GET.get('date', '').strip()
    if date_filter == 'today':
        queryset = queryset.filter(created_at__date=timezone.now().date())
    elif date_filter == 'yesterday':
        queryset = queryset.filter(created_at__date=timezone.now().date() - timezone.timedelta(days=1))

    # Pagination
    paginator = Paginator(queryset, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    terminals = Terminal.objects.filter(is_active=True)

    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'payment_method': method,
        'terminal_id': terminal_id,
        'date_filter': date_filter,
        'terminals': terminals,
        'total_count': queryset.count(),
        'total_sum': queryset.filter(status='SUCCESS').aggregate(total=Sum('amount'))['total'] or 0,
    }
    return render(request, 'payments/transactions.html', context)


def export_transactions_csv(request):
    """Export transactions list to CSV file"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="moniepoint_payments_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Merchant Reference', 'Moniepoint Ref', 'Terminal Serial', 'Terminal Name',
        'Amount (NGN)', 'Payment Method', 'Transaction Type', 'Status',
        'RRN', 'Card Type', 'Customer/Note', 'Date & Time'
    ])

    queryset = Transaction.objects.all().select_related('terminal')
    for txn in queryset:
        writer.writerow([
            txn.merchant_reference,
            txn.moniepoint_reference or '',
            txn.terminal_serial,
            txn.terminal.name if txn.terminal else 'Unassigned',
            f"{txn.amount:.2f}",
            txn.get_payment_method_display(),
            txn.get_transaction_type_display(),
            txn.status,
            txn.rrn or '',
            txn.card_type or '',
            txn.customer_name or '',
            txn.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])

    return response


def terminals_list(request):
    """POS Terminal Fleet Monitoring Overview"""
    terminals = Terminal.objects.filter(is_active=True)
    today = timezone.now().date()

    terminal_stats = []
    for term in terminals:
        txns_today = term.transactions.filter(created_at__date=today)
        total_sales = txns_today.filter(status='SUCCESS').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        success_count = txns_today.filter(status='SUCCESS').count()
        failed_count = txns_today.filter(status='FAILED').count()
        terminal_stats.append({
            'terminal': term,
            'today_sales': total_sales,
            'success_count': success_count,
            'failed_count': failed_count,
        })

    context = {
        'terminal_stats': terminal_stats,
        'config': MoniepointConfig.get_solo(),
    }
    return render(request, 'payments/terminals.html', context)


def settings_view(request):
    """Moniepoint API Configuration (.env file bound) Page"""
    config = MoniepointConfig.get_solo()

    if request.method == 'POST':
        api_key = request.POST.get('api_key', '').strip()
        business_id = request.POST.get('business_id', '').strip()
        webhook_secret = request.POST.get('webhook_secret', '').strip()
        environment = request.POST.get('environment', 'SANDBOX')

        # Persist directly into .env file
        update_env_file('MONIEPOINT_API_KEY', api_key)
        update_env_file('MONIEPOINT_BUSINESS_ID', business_id)
        update_env_file('MONIEPOINT_WEBHOOK_SECRET', webhook_secret)
        update_env_file('MONIEPOINT_ENVIRONMENT', environment)

        # Refresh model
        config = MoniepointConfig.get_solo()
        return redirect('settings')

    # Test introspection
    intro_res = MoniepointService.introspect_api_key()
    webhook_logs = WebhookLog.objects.all()[:15]
    terminals = Terminal.objects.filter(is_active=True)

    context = {
        'config': config,
        'intro_res': intro_res,
        'webhook_logs': webhook_logs,
        'terminals': terminals,
        'webhook_url': request.build_absolute_uri('/api/webhooks/moniepoint/'),
        'env_path': settings.BASE_DIR / '.env',
    }
    return render(request, 'payments/settings.html', context)


@csrf_exempt
@require_POST
def webhook_receiver(request):
    """
    Moniepoint Webhook Notification Receiver
    Endpoint: POST /api/webhooks/moniepoint/
    """
    raw_body = request.body
    signature = request.META.get('HTTP_X_MONIEPOINT_SIGNATURE', request.META.get('HTTP_SIGNATURE', ''))

    # Signature check
    is_valid = MoniepointService.verify_signature(raw_body, signature)

    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except Exception:
        payload = {}

    event_type = payload.get('eventType', payload.get('type', 'V1_POS_TRANSACTION'))

    # Save Webhook log
    log_entry = WebhookLog.objects.create(
        subscription_event_id=payload.get('subscriptionEventId', str(uuid.uuid4())),
        event_type=event_type,
        status='SUCCESS' if is_valid else 'FAILED',
        signature_valid=is_valid,
        headers=dict(request.headers),
        payload=payload
    )

    if is_valid and payload:
        MoniepointService.process_webhook_payload(payload)

    return JsonResponse({'status': 'SUCCESS', 'message': 'Webhook received successfully'}, status=200)


@require_GET
def live_feed_api(request):
    """API endpoint for live dashboard polling & real-time ticker updates"""
    today = timezone.now().date()
    today_txns = Transaction.objects.filter(created_at__date=today)
    today_success_txns = today_txns.filter(status='SUCCESS')

    today_revenue = today_success_txns.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    today_count = today_txns.count()

    recent_txns = Transaction.objects.all()[:10]
    recent_data = []
    for t in recent_txns:
        recent_data.append({
            'id': t.id,
            'ref': t.merchant_reference,
            'terminal': t.terminal.name if t.terminal else (t.terminal_serial or 'POS Terminal'),
            'amount': f"₦{t.amount:,.2f}",
            'amount_raw': float(t.amount),
            'method': t.get_payment_method_display(),
            'status': t.status,
            'rrn': t.rrn or 'N/A',
            'time': t.created_at.strftime("%H:%M:%S"),
            'date_full': t.created_at.strftime("%b %d, %Y %H:%M:%S"),
            'note': t.customer_name or 'Restaurant Sale'
        })

    return JsonResponse({
        'today_revenue': f"₦{today_revenue:,.2f}",
        'today_count': today_count,
        'recent_transactions': recent_data
    })
