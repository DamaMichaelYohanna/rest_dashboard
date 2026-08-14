import random
import uuid
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from payments.models import MoniepointConfig, Terminal, Transaction, WebhookLog

class Command(BaseCommand):
    help = 'Seed Moniepoint POS configurations, terminals, and sample restaurant payments'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Seeding Moniepoint Restaurant Payment Data..."))

        # 1. Config
        config = MoniepointConfig.get_solo()
        config.api_key = "mp_live_demo_key_9872149812739812"
        config.business_id = "1098234"
        config.webhook_secret = "whsec_demo_secret_key_8712398172938172"
        config.environment = "SANDBOX"
        config.save()

        # 2. Terminals
        terminals_data = [
            {"name": "Main Bar POS #1", "serial_number": "MP-BAR-01", "location_tag": "Main Bar", "status": "ONLINE"},
            {"name": "Dining Room POS #1", "serial_number": "MP-DINING-01", "location_tag": "Main Dining Area", "status": "ONLINE"},
            {"name": "Dining Room POS #2", "serial_number": "MP-DINING-02", "location_tag": "VIP Garden Terrace", "status": "ONLINE"},
            {"name": "Takeout & Delivery POS", "serial_number": "MP-TAKEOUT-01", "location_tag": "Front Counter", "status": "ONLINE"},
        ]

        term_objs = []
        for tdata in terminals_data:
            t, _ = Terminal.objects.update_or_create(
                serial_number=tdata["serial_number"],
                defaults={
                    "name": tdata["name"],
                    "location_tag": tdata["location_tag"],
                    "status": tdata["status"],
                    "is_active": True,
                    "last_ping": timezone.now()
                }
            )
            term_objs.append(t)

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(term_objs)} POS Terminals."))

        # 3. Sample Restaurant Transactions
        table_notes = [
            "Table 4 - 2x Jollof Rice & Grilled Chicken",
            "Bar - 4x Cold Guinness & Peppered Snail",
            "Table 12 - Chef's Special & Cocktails",
            "Takeout - 1x Egusi Soup & Pounded Yam",
            "Table 8 - Family Seafood Platter",
            "VIP Room - Wine Bottle & Suya Board",
            "Table 2 - Coffee & Cheesecake",
            "Bar - Shots & Cocktails",
            "Table 15 - Lunch Buffet x3",
            "Takeout Order #204 - Delivery",
        ]

        card_brands = ["Mastercard", "Visa", "Verve", "Bank Transfer"]

        now = timezone.now()

        # Clean existing sample txns for clean seed if needed
        # Transaction.objects.all().delete()

        created_count = 0

        # Generate txns for today across different hours
        for h in range(8, now.hour + 1):
            num_txns = random.randint(1, 4)
            for _ in range(num_txns):
                term = random.choice(term_objs)
                amount = random.choice([2500, 4800, 7500, 12000, 18500, 24000, 32000, 8900, 14200, 6500])
                payment_method = random.choice(["CARD_PURCHASE", "CARD_PURCHASE", "POS_TRANSFER"])
                status = random.choice(["SUCCESS", "SUCCESS", "SUCCESS", "SUCCESS", "SUCCESS", "FAILED"])
                
                txn_time = now.replace(hour=h, minute=random.randint(0, 59), second=random.randint(0, 59))
                m_ref = f"REST-{txn_time.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
                mp_ref = f"MP-{random.randint(1000000000, 9999999999)}"
                rrn = f"{random.randint(100000000000, 999999999999)}"
                card = random.choice(card_brands) if payment_method == 'CARD_PURCHASE' else 'Bank Transfer'
                pan = f"5399****{random.randint(1000, 9999)}" if payment_method == 'CARD_PURCHASE' else ''

                Transaction.objects.update_or_create(
                    merchant_reference=m_ref,
                    defaults={
                        "moniepoint_reference": mp_ref,
                        "terminal": term,
                        "terminal_serial": term.serial_number,
                        "amount": Decimal(amount),
                        "payment_method": payment_method,
                        "transaction_type": "PURCHASE",
                        "status": status,
                        "response_code": "00" if status == "SUCCESS" else "51",
                        "response_message": "Approved" if status == "SUCCESS" else "Insufficient Funds",
                        "rrn": rrn,
                        "card_type": card,
                        "masked_pan": pan,
                        "customer_name": random.choice(table_notes),
                        "created_at": txn_time
                    }
                )
                created_count += 1

        # Generate txns for yesterday
        yesterday = now - timezone.timedelta(days=1)
        for h in range(9, 23):
            for _ in range(random.randint(1, 3)):
                term = random.choice(term_objs)
                amount = random.choice([3500, 8800, 15000, 21000, 9500])
                payment_method = random.choice(["CARD_PURCHASE", "POS_TRANSFER"])
                txn_time = yesterday.replace(hour=h, minute=random.randint(0, 59))
                m_ref = f"REST-{txn_time.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

                Transaction.objects.update_or_create(
                    merchant_reference=m_ref,
                    defaults={
                        "moniepoint_reference": f"MP-{random.randint(1000000000, 9999999999)}",
                        "terminal": term,
                        "terminal_serial": term.serial_number,
                        "amount": Decimal(amount),
                        "payment_method": payment_method,
                        "transaction_type": "PURCHASE",
                        "status": "SUCCESS",
                        "response_code": "00",
                        "response_message": "Approved",
                        "rrn": f"{random.randint(100000000000, 999999999999)}",
                        "card_type": "Mastercard" if payment_method == 'CARD_PURCHASE' else 'Bank Transfer',
                        "customer_name": random.choice(table_notes),
                        "created_at": txn_time
                    }
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {created_count} sample transactions!"))
