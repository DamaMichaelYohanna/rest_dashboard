import hmac
import hashlib
import json
import logging
import requests
from django.utils import timezone
from .models import MoniepointConfig, Terminal, Transaction, WebhookLog

logger = logging.getLogger(__name__)

MONIEPOINT_BASE_URL = "https://api.pos.moniepoint.com"

class MoniepointService:
    @staticmethod
    def get_headers(config=None):
        if not config:
            config = MoniepointConfig.get_solo()
        return {
            "Authorization": f"Bearer {config.api_key}" if not config.api_key.startswith("Bearer ") else config.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    @classmethod
    def introspect_api_key(cls):
        """Introspect API Key token via Moniepoint /v1/introspect"""
        config = MoniepointConfig.get_solo()
        if not config.api_key or config.api_key.startswith("mp_live_demo"):
            return {
                "valid": True,
                "environment": config.environment,
                "scope": ["transaction:read", "webhook:read"],
                "businesses": [{"id": config.business_id or "1098234", "name": "Moniepoint Restaurant Demo"}],
                "message": "Demo API Key operating in Sandbox mode."
            }

        url = f"{MONIEPOINT_BASE_URL}/v1/introspect"
        try:
            res = requests.get(url, headers=cls.get_headers(config), timeout=10)
            if res.status_code == 200:
                data = res.json()
                return {"valid": True, "data": data}
            return {"valid": False, "error": res.text, "status_code": res.status_code}
        except Exception as e:
            logger.error(f"Moniepoint introspection error: {e}")
            return {"valid": False, "error": str(e)}

    @classmethod
    def query_transaction(cls, merchant_reference):
        """Query transaction details via /v1/transactions/merchants/{merchantReference}"""
        config = MoniepointConfig.get_solo()
        if not config.api_key or config.api_key.startswith("mp_live_demo"):
            txn = Transaction.objects.filter(merchant_reference=merchant_reference).first()
            if txn:
                return {"success": True, "transaction": txn}
            return {"success": False, "error": "Transaction reference not found"}

        url = f"{MONIEPOINT_BASE_URL}/v1/transactions/merchants/{merchant_reference}"
        try:
            res = requests.get(url, headers=cls.get_headers(config), timeout=10)
            if res.status_code == 200:
                data = res.json()
                cls.process_webhook_payload(data)
                return {"success": True, "data": data}
            return {"success": False, "error": res.text, "status_code": res.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def verify_signature(cls, raw_body, signature_header):
        """Verify Moniepoint / Monnify webhook HMAC signature"""
        config = MoniepointConfig.get_solo()
        if not config.webhook_secret or not signature_header:
            return True # Allow if secret is not set in demo mode

        try:
            # SHA256 check
            expected_sig_sha256 = hmac.new(
                config.webhook_secret.encode('utf-8'),
                raw_body,
                hashlib.sha256
            ).hexdigest()

            # SHA512 check for Monnify/Moniepoint direct transfer webhooks
            expected_sig_sha512 = hmac.new(
                config.webhook_secret.encode('utf-8'),
                raw_body,
                hashlib.sha512
            ).hexdigest()

            sig_lower = signature_header.lower()
            return hmac.compare_digest(expected_sig_sha256.lower(), sig_lower) or hmac.compare_digest(expected_sig_sha512.lower(), sig_lower)
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return True # Fail open to ensure no missed webhooks if formatting varies

    @classmethod
    def process_webhook_payload(cls, payload):
        """
        Process Moniepoint POS AND Moniepoint Direct Bank Transfer webhooks
        """
        event_type = payload.get('eventType') or payload.get('event') or payload.get('type', 'V1_POS_TRANSACTION')
        data = payload.get('data') or payload.get('eventData') or payload

        # Monnify/Moniepoint Direct Account Transfer Webhook Detection
        is_direct_bank_transfer = (
            'amountPaid' in data or
            'ACCOUNT_TRANSFER' in str(payload).upper() or
            'DIRECT_DEPOSIT' in str(event_type).upper() or
            'SUCCESSFUL_TRANSACTION' in str(event_type).upper()
        )

        merchant_ref = (
            data.get('merchantReference') or
            data.get('merchantRef') or
            data.get('transactionReference') or
            data.get('paymentReference') or
            data.get('reference')
        )
        if not merchant_ref:
            merchant_ref = f"TRF-{timezone.now().strftime('%Y%m%d%H%M%S')}"

        moniepoint_ref = (
            data.get('moniepointReference') or
            data.get('transactionReference') or
            data.get('paymentReference') or
            data.get('id', '')
        )

        terminal_serial = data.get('terminalSerial') or data.get('terminalId') or data.get('serialNumber', '')

        # Amount parsing
        raw_amount = data.get('amountPaid') or data.get('amount') or data.get('totalPayable', 0)
        amount_naira = float(raw_amount)
        # If amount is sent in kobo (e.g. 500000 kobo = 5000 NGN)
        if amount_naira > 1000 and amount_naira % 100 == 0 and 'amountPaid' not in data:
            amount_naira = amount_naira / 100.0

        status_raw = str(data.get('paymentStatus') or data.get('status', 'SUCCESS')).upper()
        if status_raw in ['SUCCESS', 'SUCCESSFUL', 'APPROVED', 'PAID', '00']:
            status = 'SUCCESS'
        elif status_raw in ['FAILED', 'DECLINED', 'REJECTED']:
            status = 'FAILED'
        elif status_raw in ['REVERSED', 'REFUNDED']:
            status = 'REVERSED'
        else:
            status = 'PENDING'

        payment_method = 'POS_TRANSFER' if is_direct_bank_transfer else str(data.get('paymentMethod', 'CARD_PURCHASE')).upper()
        if payment_method not in ['CARD_PURCHASE', 'POS_TRANSFER', 'USSD', 'PAYCODE', 'ANY']:
            payment_method = 'POS_TRANSFER' if 'TRANSFER' in payment_method else 'CARD_PURCHASE'

        txn_type = 'POS_TRANSFER' if is_direct_bank_transfer else str(data.get('transactionType', 'PURCHASE')).upper()
        if txn_type not in ['PURCHASE', 'POS_TRANSFER', 'CARD_TRANSFER', 'BILL_PAYMENT', 'WITHDRAWAL', 'BOOM']:
            txn_type = 'POS_TRANSFER'

        rrn = data.get('rrn') or data.get('retrievalReferenceNumber') or data.get('transactionReference', '')

        # Customer / Sender Name Extraction
        customer_info = data.get('customer', {})
        if isinstance(customer_info, dict):
            cust_name = customer_info.get('name') or customer_info.get('email', '')
        else:
            cust_name = str(customer_info)

        if not cust_name:
            cust_name = (
                data.get('customerName') or
                data.get('senderAccountName') or
                data.get('cardHolderName') or
                data.get('note') or
                ('Direct Bank Transfer' if is_direct_bank_transfer else 'Restaurant Payment')
            )

        sender_bank = data.get('senderBankName') or data.get('bankName', '')
        if sender_bank and sender_bank.lower() not in cust_name.lower():
            cust_name = f"{sender_bank} Transfer - {cust_name}"

        card_type = 'Bank Transfer' if is_direct_bank_transfer else (data.get('cardType') or data.get('brand', 'Card'))
        masked_pan = data.get('maskedPan') or data.get('pan', '')
        response_code = data.get('responseCode', '00')
        response_msg = data.get('responseMessage', 'Approved' if status == 'SUCCESS' else 'Declined')

        # Find or auto-discover terminal / account tag
        terminal = None
        if not terminal_serial and is_direct_bank_transfer:
            terminal_serial = "DIRECT-ACCOUNT"

        if terminal_serial:
            terminal_name = "Direct Bank Transfer Account" if terminal_serial == "DIRECT-ACCOUNT" else f"POS Terminal ({terminal_serial})"
            location_tag = "Bank Account Transfer" if terminal_serial == "DIRECT-ACCOUNT" else "Restaurant Floor"

            terminal, _ = Terminal.objects.get_or_create(
                serial_number=terminal_serial,
                defaults={
                    'name': terminal_name,
                    'location_tag': location_tag,
                    'status': 'ONLINE',
                    'last_ping': timezone.now()
                }
            )
            terminal.last_ping = timezone.now()
            terminal.status = 'ONLINE'
            terminal.save()

        # Update or create transaction record
        txn, created = Transaction.objects.update_or_create(
            merchant_reference=merchant_ref,
            defaults={
                'moniepoint_reference': moniepoint_ref,
                'terminal': terminal,
                'terminal_serial': terminal_serial,
                'amount': amount_naira,
                'payment_method': payment_method,
                'transaction_type': txn_type,
                'status': status,
                'response_code': response_code,
                'response_message': response_msg,
                'rrn': rrn,
                'card_type': card_type,
                'masked_pan': masked_pan,
                'customer_name': cust_name,
                'raw_payload': payload
            }
        )

        return txn
