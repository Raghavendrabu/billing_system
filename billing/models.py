from django.db import models
from django.utils import timezone
from datetime import timedelta

class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True, primary_key=True)
    name = models.CharField(max_length=150)
    rate = models.DecimalField(max_digits=10, decimal_places=2) # Base Price
    tax_code = models.DecimalField(max_digits=5, decimal_places=2, default=18.00) # GST percentage (e.g., 18.00 for 18%)
    current_stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"

class Customer(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    lifetime_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    loyalty_points = models.IntegerField(default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name

class Invoice(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('Paid', 'Paid'),
        ('Pending', 'Pending'),
        ('Failed', 'Failed'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('UPI', 'UPI'),
        ('Loyalty Points', 'Loyalty Points'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2) # Total GST (CGST + SGST or IGST)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Paid')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='UPI')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.invoice_number

    @property
    def cgst(self):
        # CGST is half of tax_amount (assuming intra-state transaction)
        return self.tax_amount / 2

    @property
    def sgst(self):
        # SGST is half of tax_amount
        return self.tax_amount / 2

    @property
    def whatsapp_phone(self):
        if not self.customer or not self.customer.phone:
            return ""
        # Strip all non-digit characters
        phone_digits = "".join(c for c in self.customer.phone if c.isdigit())
        # If it doesn't start with 91 and has 10 digits, prepend 91 (for India)
        if len(phone_digits) == 10:
            phone_digits = "91" + phone_digits
        return phone_digits

    @property
    def whatsapp_text(self):
        date_str = self.created_at.strftime('%d %b %Y')
        due_date = self.created_at + timedelta(days=10)
        due_str = due_date.strftime('%d %b %Y')
        
        # Calculate earned points (1 point per 10 INR spent)
        earned_points = int(self.total_amount / 10)
        
        # Build text matching your layout exactly
        text = f"📄 📝 New Invoice from Smart Billing\n\n"
        text += f"📌 Invoice #: {self.invoice_number}\n"
        text += f"📅 Date: {date_str}\n"
        text += f"💰 Amount: ₹{self.total_amount:.2f}\n"
        text += f"⏰ Due Date: {due_str}\n\n"
        text += f"🔗 Payment Link: http://127.0.0.1:8000/invoice/{self.id}/pdf/\n\n"
        text += f"📎 Invoice_{self.invoice_number}.pdf\n"
        text += f"[Document] 245 KB\n\n"
        text += f"⭐ Loyalty Points: {earned_points} earned\n\n"
        text += f"🙏 Thank you for your business"
        return text

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2) # Price of product at time of sale
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2) # Tax percentage at time of sale
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2) # Calculated tax for this quantity
    total_price = models.DecimalField(max_digits=12, decimal_places=2) # (unit_price * quantity) + tax_amount

    def __str__(self):
        return f"{self.product.name if self.product else 'Deleted Product'} x {self.quantity}"

class TransactionAlert(models.Model):
    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('danger', 'Danger'),
    ]
    message = models.CharField(max_length=255)
    level = models.CharField(max_length=15, choices=LEVEL_CHOICES, default='info')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.level.upper()}] {self.message}"

class LoyaltyTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('Earned', 'Earned'),
        ('Redeemed', 'Redeemed'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loyalty_history')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    points = models.IntegerField() # Positive for earned, negative for redeemed
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='Earned')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.name} - {self.points} points ({self.transaction_type})"
