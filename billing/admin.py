from django.contrib import admin
from .models import Product, Customer, Invoice, InvoiceItem, TransactionAlert, LoyaltyTransaction

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'rate', 'tax_code', 'current_stock', 'is_active')
    search_fields = ('name', 'sku')
    list_filter = ('is_active',)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'lifetime_value', 'loyalty_points')
    search_fields = ('name', 'email', 'phone')

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer', 'total_amount', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('invoice_number', 'customer__name')
    list_filter = ('payment_status', 'payment_method')
    inlines = [InvoiceItemInline]

@admin.register(TransactionAlert)
class TransactionAlertAdmin(admin.ModelAdmin):
    list_display = ('message', 'level', 'created_at')
    list_filter = ('level',)

@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'points', 'transaction_type', 'created_at')
    list_filter = ('transaction_type',)
