from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Invoice, InvoiceItem, Product, Customer, TransactionAlert, LoyaltyTransaction
from decimal import Decimal

@receiver(post_save, sender=Invoice)
def handle_invoice_payment(sender, instance, created, **kwargs):
    if instance.payment_status == 'Paid' and instance.customer:
        customer = instance.customer
        
        # Calculate points to award or redeem
        if instance.payment_method == 'Loyalty Points':
            # Redeem points: let's assume 1 point = 1 unit of currency
            # We redeem points equal to the total invoice amount
            redeemed_points = int(instance.total_amount)
            if customer.loyalty_points >= redeemed_points:
                customer.loyalty_points -= redeemed_points
                # Record transaction
                LoyaltyTransaction.objects.create(
                    customer=customer,
                    invoice=instance,
                    points=-redeemed_points,
                    transaction_type='Redeemed'
                )
                # Create alert
                TransactionAlert.objects.create(
                    message=f"Customer {customer.name} redeemed {redeemed_points} loyalty points for Invoice {instance.invoice_number}",
                    level='info'
                )
        else:
            # Earn points: 1 point for every 10 units of currency spent
            earned_points = int(instance.total_amount / 10)
            if earned_points > 0:
                customer.loyalty_points += earned_points
                # Record transaction
                LoyaltyTransaction.objects.create(
                    customer=customer,
                    invoice=instance,
                    points=earned_points,
                    transaction_type='Earned'
                )
        
        # Update lifetime value
        customer.lifetime_value += instance.total_amount
        customer.save()

@receiver(post_save, sender=InvoiceItem)
def handle_stock_reduction(sender, instance, created, **kwargs):
    if created and instance.product:
        product = instance.product
        # Deduct stock
        product.current_stock -= instance.quantity
        product.save()
        
        # Trigger system alert if stock is low
        if product.current_stock < 15:
            # Avoid duplicate warnings in the same session by checking if a warning already exists
            # We can create a warning alert
            level = 'danger' if product.current_stock <= 5 else 'warning'
            TransactionAlert.objects.create(
                message=f"Low Stock: {product.name} ({product.sku}) is running low! Only {product.current_stock} units left.",
                level=level
            )
