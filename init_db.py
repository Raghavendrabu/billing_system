import os
import django
import random
from django.utils import timezone
from datetime import timedelta

# Bootstrap Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_billing.settings')
django.setup()

# Import models
from billing.models import Product, Customer, Invoice, InvoiceItem, TransactionAlert, LoyaltyTransaction
from django.db.models.signals import post_save
from billing.signals import handle_invoice_payment, handle_stock_reduction

def seed_database():
    print("Muting Django Database Signals for clean data seeding...")
    # Disconnect signals to avoid automated stock reduction / double loyalty point awarding during seeding
    post_save.disconnect(handle_invoice_payment, sender=Invoice)
    post_save.disconnect(handle_stock_reduction, sender=InvoiceItem)

    print("Cleaning database...")
    LoyaltyTransaction.objects.all().delete()
    TransactionAlert.objects.all().delete()
    InvoiceItem.objects.all().delete()
    Invoice.objects.all().delete()
    Customer.objects.all().delete()
    Product.objects.all().delete()

    print("Seeding Products...")
    products = [
        Product(sku='SKU001', name='Product A - Widget', rate=400.00, tax_code=18.00, current_stock=10, is_active=True),
        Product(sku='SKU002', name='Product B - Tool', rate=1200.00, tax_code=12.00, current_stock=24, is_active=True),
        Product(sku='SKU003', name='Product C - Gadget', rate=1500.00, tax_code=18.00, current_stock=30, is_active=True),
        Product(sku='SKU004', name='Product D - Gizmo', rate=850.00, tax_code=5.00, current_stock=13, is_active=True),
        Product(sku='SKU005', name='Product E - Device', rate=12000.00, tax_code=18.00, current_stock=3, is_active=True),
        Product(sku='SKU006', name='Product F - Instrument', rate=4500.00, tax_code=12.00, current_stock=18, is_active=True),
        Product(sku='SKU007', name='Product G - Adapter', rate=750.00, tax_code=18.00, current_stock=42, is_active=True),
        Product(sku='SKU008', name='Product H - Sensor', rate=2200.00, tax_code=18.00, current_stock=5, is_active=True),
    ]
    for p in products:
        p.save()
    print(f"Seeded {len(products)} products.")

    print("Seeding Indian Customers...")
    customers = [
        Customer(name='Rahul Sharma', email='rahul.sharma@gmail.com', phone='+91 98765 43210', lifetime_value=31600.00, loyalty_points=310, balance=0.00),
        Customer(name='Priya Patel', email='priya.patel@yahoo.co.in', phone='+91 87654 32109', lifetime_value=25000.00, loyalty_points=250, balance=150.00),
        Customer(name='Amit Verma', email='amit.verma@outlook.com', phone='+91 76543 21098', lifetime_value=125000.00, loyalty_points=1250, balance=500.00),
        Customer(name='Sneha Reddy', email='sneha.reddy@gmail.com', phone='+91 91234 56789', lifetime_value=7500.00, loyalty_points=75, balance=0.00),
        Customer(name='Vikram Malhotra', email='vikram.m@gmail.com', phone='+91 99887 76655', lifetime_value=0.00, loyalty_points=0, balance=0.00),
    ]
    for c in customers:
        c.save()
    print(f"Seeded {len(customers)} Indian customers.")

    print("Seeding Transactional Invoices in INR...")
    dates = [
        timezone.now() - timedelta(minutes=15),
        timezone.now() - timedelta(hours=3),
        timezone.now() - timedelta(days=1),
        timezone.now() - timedelta(days=3),
        timezone.now() - timedelta(days=7),
    ]

    methods = ['UPI', 'Card', 'Cash', 'UPI', 'Loyalty Points']
    statuses = ['Paid', 'Paid', 'Paid', 'Paid', 'Paid']
    
    # Create Invoice 1
    i1 = Invoice.objects.create(
        invoice_number="INV-2605230001",
        customer=customers[0],
        subtotal=6000.00,
        tax_amount=960.00,
        discount_amount=500.00,
        total_amount=6460.00,
        payment_status=statuses[0],
        payment_method=methods[0],
        created_at=dates[0]
    )
    InvoiceItem.objects.create(invoice=i1, product=products[0], quantity=1, unit_price=400.00, tax_rate=18.00, tax_amount=72.00, total_price=472.00)
    InvoiceItem.objects.create(invoice=i1, product=products[2], quantity=2, unit_price=1500.00, tax_rate=18.00, tax_amount=540.00, total_price=3540.00)
    InvoiceItem.objects.create(invoice=i1, product=products[1], quantity=2, unit_price=1200.00, tax_rate=12.00, tax_amount=288.00, total_price=2688.00)
    
    # Create Invoice 2
    i2 = Invoice.objects.create(
        invoice_number="INV-2605230002",
        customer=customers[1],
        subtotal=12000.00,
        tax_amount=2160.00,
        discount_amount=0.00,
        total_amount=14160.00,
        payment_status=statuses[1],
        payment_method=methods[1],
        created_at=dates[1]
    )
    InvoiceItem.objects.create(invoice=i2, product=products[4], quantity=1, unit_price=12000.00, tax_rate=18.00, tax_amount=2160.00, total_price=14160.00)
    
    # Create Invoice 3
    i3 = Invoice.objects.create(
        invoice_number="INV-2605230003",
        customer=customers[2],
        subtotal=4400.00,
        tax_amount=792.00,
        discount_amount=1000.00,
        total_amount=4192.00,
        payment_status=statuses[2],
        payment_method=methods[2],
        created_at=dates[2]
    )
    InvoiceItem.objects.create(invoice=i3, product=products[7], quantity=2, unit_price=2200.00, tax_rate=18.00, tax_amount=792.00, total_price=5192.00)

    # Create Invoice 4
    i4 = Invoice.objects.create(
        invoice_number="INV-2605230004",
        customer=customers[3],
        subtotal=750.00,
        tax_amount=135.00,
        discount_amount=0.00,
        total_amount=885.00,
        payment_status=statuses[3],
        payment_method=methods[3],
        created_at=dates[3]
    )
    InvoiceItem.objects.create(invoice=i4, product=products[6], quantity=1, unit_price=750.00, tax_rate=18.00, tax_amount=135.00, total_price=885.00)

    print("Seeded Invoices history in INR.")

    print("Seeding System Alerts Feed...")
    alerts = [
        TransactionAlert(message="Low Stock: Product E - Device (SKU005) is running low! Only 3 units left.", level='danger', created_at=timezone.now() - timedelta(minutes=5)),
        TransactionAlert(message="Low Stock: Product H - Sensor (SKU008) is running low! Only 5 units left.", level='warning', created_at=timezone.now() - timedelta(hours=1)),
        TransactionAlert(message="New Registered Client Rahul Sharma joined the VIP Loyalty Program.", level='info', created_at=timezone.now() - timedelta(hours=4)),
        TransactionAlert(message="GST Tax Compliance Audit: Completed successfully for current billing period.", level='info', created_at=timezone.now() - timedelta(days=1)),
    ]
    for a in alerts:
        a.save()
    print("Seeded System Alerts.")

    # Re-connect signals
    print("Re-connecting Database Signals...")
    post_save.connect(handle_invoice_payment, sender=Invoice)
    post_save.connect(handle_stock_reduction, sender=InvoiceItem)

    print("\nDatabase Seeding Completed Successfully! All mock records are in place.")

if __name__ == "__main__":
    seed_database()
