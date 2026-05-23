import io
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.db import transaction
from django.db.models import Sum, Avg, Q
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

# Import models
from .models import Product, Customer, Invoice, InvoiceItem, TransactionAlert, LoyaltyTransaction

# Import ReportLab modules for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def dashboard_view(request):
    # Calculate operational metrics
    total_rev = Invoice.objects.filter(payment_status='Paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00
    avg_sale = Invoice.objects.filter(payment_status='Paid').aggregate(Avg('total_amount'))['total_amount__avg'] or 0.00
    active_stock = Product.objects.filter(is_active=True).count()
    cust_count = Customer.objects.count()
    
    metrics = {
        'total_revenue': f"{total_rev:,.2f}",
        'avg_sale': f"{avg_sale:,.2f}",
        'active_stock': active_stock,
        'customers_count': cust_count
    }
    
    # Low stock counts
    low_stock_count = Product.objects.filter(current_stock__lt=15).count()
    
    # Recent paid invoices
    recent_invoices = Invoice.objects.all().order_by('-created_at')[:5]
    
    # Active system alerts
    alerts = TransactionAlert.objects.all().order_by('-created_at')[:8]
    
    # Select options for Quick Invoice Form
    products = Product.objects.filter(is_active=True, current_stock__gt=0)
    customers = Customer.objects.all().order_by('name')
    
    context = {
        'active_page': 'dashboard',
        'metrics': metrics,
        'low_stock_count': low_stock_count,
        'recent_invoices': recent_invoices,
        'alerts': alerts,
        'products': products,
        'customers': customers
    }
    return render(request, 'dashboard.html', context)

def product_list_view(request):
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('stock_filter', 'all')
    
    products = Product.objects.all().order_by('name')
    
    # Apply search filter
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(sku__icontains=search_query)
        )
        
    # Apply stock category filter
    if status_filter == 'low':
        products = products.filter(current_stock__lt=15)
    elif status_filter == 'out':
        products = products.filter(current_stock=0)
    elif status_filter == 'active':
        products = products.filter(is_active=True)
        
    low_stock_count = Product.objects.filter(current_stock__lt=15).count()
    
    context = {
        'active_page': 'products',
        'products': products,
        'low_stock_count': low_stock_count,
        'search_query': search_query,
        'status_filter': status_filter
    }
    
    # Check if this is an HTMX request to return the partial table only
    if request.headers.get('HX-Request'):
        return render(request, 'partials/products_table.html', context)
        
    return render(request, 'products.html', context)

def customer_list_view(request):
    search_query = request.GET.get('search', '').strip()
    customers = Customer.objects.all().order_by('name')
    
    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
        
    # Stats summaries
    total_points = Customer.objects.aggregate(Sum('loyalty_points'))['loyalty_points__sum'] or 0
    top_customers = Customer.objects.all().order_by('-lifetime_value')[:5]
    
    context = {
        'active_page': 'customers',
        'customers': customers,
        'total_loyalty_points': total_points,
        'top_customers': top_customers,
        'search_query': search_query
    }
    
    # Check if HTMX request
    if request.headers.get('HX-Request'):
        return render(request, 'partials/customers_table.html', context)
        
    return render(request, 'customers.html', context)

@csrf_exempt
def save_product_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        sku = request.POST.get('sku').strip()
        name = request.POST.get('name').strip()
        rate = float(request.POST.get('rate') or 0.0)
        tax_code = float(request.POST.get('tax_code') or 18.0)
        
        if action == 'edit':
            sku_original = request.POST.get('sku_original')
            prod = get_object_or_404(Product, sku=sku_original)
            prod.name = name
            prod.rate = rate
            prod.tax_code = tax_code
            prod.is_active = request.POST.get('is_active') == 'true'
            prod.save()
            messages.success(request, f"Product {name} updated successfully.")
        else:
            current_stock = int(request.POST.get('current_stock') or 0)
            is_active = request.POST.get('is_active') == 'true'
            Product.objects.create(
                sku=sku,
                name=name,
                rate=rate,
                tax_code=tax_code,
                current_stock=current_stock,
                is_active=is_active
            )
            messages.success(request, f"Product {name} registered successfully.")
            
    return redirect('products')

@csrf_exempt
def adjust_stock_view(request):
    if request.method == 'POST':
        sku = request.POST.get('sku')
        adjustment = int(request.POST.get('adjustment') or 0)
        
        prod = get_object_or_404(Product, sku=sku)
        prod.current_stock += adjustment
        prod.save()
        
        # Log stock adjustment warning if it reduced significantly
        if adjustment < 0:
            TransactionAlert.objects.create(
                message=f"Manual Stock Correction: Decreased {prod.name} ({prod.sku}) by {abs(adjustment)} qty. Current: {prod.current_stock}.",
                level='warning' if prod.current_stock > 10 else 'danger'
            )
        else:
            TransactionAlert.objects.create(
                message=f"Stock Restocked: Restocked {prod.name} ({prod.sku}) by +{adjustment} qty. Current: {prod.current_stock}.",
                level='info'
            )
            
        messages.success(request, f"Adjusted stock for {prod.name} by {adjustment:+}.")
        
    return redirect('products')

@csrf_exempt
def save_customer_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        name = request.POST.get('name').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        
        if action == 'edit':
            cust_id = request.POST.get('customer_id')
            cust = get_object_or_404(Customer, id=cust_id)
            cust.name = name
            cust.email = email if email else None
            cust.phone = phone if phone else None
            cust.save()
            messages.success(request, f"Customer {name} updated.")
        else:
            points = int(request.POST.get('loyalty_points') or 0)
            balance = float(request.POST.get('balance') or 0.0)
            Customer.objects.create(
                name=name,
                email=email if email else None,
                phone=phone if phone else None,
                loyalty_points=points,
                balance=balance
            )
            messages.success(request, f"New customer {name} registered.")
            
    return redirect('customers')

@csrf_exempt
@transaction.atomic
def create_invoice_view(request):
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        payment_method = request.POST.get('payment_method', 'UPI')
        discount = float(request.POST.get('discount') or 0.0)
        items_count = int(request.POST.get('items_count') or 0)
        
        # Calculate matching transaction figures
        subtotal = float(request.POST.get('subtotal_val') or 0.0)
        tax = float(request.POST.get('tax_val') or 0.0)
        total = float(request.POST.get('total_val') or 0.0)
        
        # Customer bindings
        customer = None
        if customer_id:
            customer = get_object_or_404(Customer, id=customer_id)
            
        # Create invoice number unique serial
        inv_number = f"INV-{timezone.now().strftime('%y%m%d%H%M%S')}"
        
        # Create Invoice
        invoice = Invoice.objects.create(
            invoice_number=inv_number,
            customer=customer,
            subtotal=subtotal,
            tax_amount=tax,
            discount_amount=discount,
            total_amount=total,
            payment_status='Paid', # default paid for checkout drawer
            payment_method=payment_method
        )
        
        # Create Invoice Items
        for i in range(items_count):
            prod_sku = request.POST.get(f'item_product_{i}')
            qty = int(request.POST.get(f'item_qty_{i}') or 1)
            
            if prod_sku:
                prod = get_object_or_404(Product, sku=prod_sku)
                item_subtotal = float(prod.rate) * qty
                item_tax = item_subtotal * (float(prod.tax_code) / 100.0)
                item_total = item_subtotal + item_tax
                
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=prod,
                    quantity=qty,
                    unit_price=prod.rate,
                    tax_rate=prod.tax_code,
                    tax_amount=item_tax,
                    total_price=item_total
                )
                
        # Audit logs
        TransactionAlert.objects.create(
            message=f"Checkout Completed: Invoice {inv_number} processed for ₹{total:.2f} using {payment_method}.",
            level='info'
        )
        messages.success(request, f"Invoice {inv_number} created successfully.")
        
    return redirect('dashboard')

def generate_pdf_report_view(request):
    report_type = request.GET.get('report_type', 'sales')
    time_window = request.GET.get('time_window', 'all')
    
    # Configure buffer
    buffer = io.BytesIO()
    
    # Setup document
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=0.5*inch, 
        leftMargin=0.5*inch, 
        topMargin=0.75*inch, 
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette Accent Styles
    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#1e1b4b'),
        spaceAfter=6,
        alignment=0
    )
    
    style_subtitle = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.HexColor('#6366f1'),
        spaceAfter=15,
        alignment=0
    )
    
    style_normal = styles['Normal']
    
    elements = []
    
    # Header Banner Block
    elements.append(Paragraph("SMART BILLING AUDITING SUITE v1.1", style_title))
    elements.append(Paragraph(f"AUDIT TYPE: {report_type.upper()} REPORT | COMPILED DATE: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", style_subtitle))
    elements.append(Spacer(1, 15))
    
    # Table styles variables
    header_color = colors.HexColor('#4f46e5')
    text_color = colors.HexColor('#1f2937')
    line_color = colors.HexColor('#e5e7eb')
    
    if report_type == 'sales':
        # Compile Sales Report
        invoices = Invoice.objects.all().order_by('-created_at')
        total_revenue = invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00
        avg_basket = invoices.aggregate(Avg('total_amount'))['total_amount__avg'] or 0.00
        tax_total = invoices.aggregate(Sum('tax_amount'))['tax_amount__sum'] or 0.00
        
        # Summary Grid
        summary_data = [
            [Paragraph("<b>Total Volume Sold:</b>", style_normal), Paragraph(f"Rs. {total_revenue:,.2f}", style_normal)],
            [Paragraph("<b>Average Basket Value:</b>", style_normal), Paragraph(f"Rs. {avg_basket:,.2f}", style_normal)],
            [Paragraph("<b>GST Tax Collected:</b>", style_normal), Paragraph(f"Rs. {tax_total:,.2f}", style_normal)],
            [Paragraph("<b>Transaction Count:</b>", style_normal), Paragraph(str(invoices.count()), style_normal)]
        ]
        
        sum_table = Table(summary_data, colWidths=[200, 200])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f3f4f6')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e5e7eb')),
        ]))
        elements.append(sum_table)
        elements.append(Spacer(1, 20))
        
        # Detailed Sales Table
        elements.append(Paragraph("<b>Detailed Invoices Log</b>", styles['Heading3']))
        elements.append(Spacer(1, 8))
        
        table_data = [['Invoice ID', 'Date', 'Customer Name', 'Subtotal', 'Tax', 'Grand Total', 'Status']]
        for inv in invoices:
            table_data.append([
                inv.invoice_number,
                inv.created_at.strftime('%Y-%m-%d'),
                inv.customer.name if inv.customer else 'Retail Walk-in',
                f"Rs. {inv.subtotal:.2f}",
                f"Rs. {inv.tax_amount:.2f}",
                f"Rs. {inv.total_amount:.2f}",
                inv.payment_status
            ])
            
        t = Table(table_data, colWidths=[100, 75, 120, 60, 60, 75, 60])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), header_color),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('BACKGROUND', (0,1), (-1,-1), colors.white),
            ('GRID', (0,0), (-1,-1), 0.5, line_color),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
            ('FONTSIZE', (0,1), (-1,-1), 8),
        ]))
        elements.append(t)
        
    elif report_type == 'inventory':
        products = Product.objects.all().order_by('name')
        
        # Summary
        low_count = products.filter(current_stock__lt=15).count()
        tot_count = products.count()
        
        summary_data = [
            [Paragraph("<b>Total Product Categories:</b>", style_normal), Paragraph(str(tot_count), style_normal)],
            [Paragraph("<b>Low Stock Alerts Active:</b>", style_normal), Paragraph(f"<font color='red'><b>{low_count} items</b></font>", style_normal)]
        ]
        sum_table = Table(summary_data, colWidths=[200, 200])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f3f4f6')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e5e7eb')),
        ]))
        elements.append(sum_table)
        elements.append(Spacer(1, 20))
        
        # Detailed Table
        elements.append(Paragraph("<b>Stock Assets Registry Log</b>", styles['Heading3']))
        elements.append(Spacer(1, 8))
        
        table_data = [['SKU Code', 'Listing Name', 'Base Price', 'GST Rate', 'Stock Balance', 'Listing Status']]
        for prod in products:
            table_data.append([
                prod.sku,
                prod.name,
                f"Rs. {prod.rate:.2f}",
                f"{prod.tax_code}%",
                f"{prod.current_stock} qty",
                'Active' if prod.is_active else 'Archived'
            ])
            
        t = Table(table_data, colWidths=[80, 200, 70, 60, 70, 70])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), header_color),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, line_color),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
            ('FONTSIZE', (0,0), (-1,-1), 8),
        ]))
        elements.append(t)
        
    elif report_type == 'loyalty':
        customers = Customer.objects.all().order_by('-lifetime_value')
        
        # Summary
        total_pts = Customer.objects.aggregate(Sum('loyalty_points'))['loyalty_points__sum'] or 0
        summary_data = [
            [Paragraph("<b>Total Registered Members:</b>", style_normal), Paragraph(str(customers.count()), style_normal)],
            [Paragraph("<b>Total Loyalty Points Circulating:</b>", style_normal), Paragraph(f"{total_pts} pts", style_normal)]
        ]
        sum_table = Table(summary_data, colWidths=[200, 200])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f3f4f6')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e5e7eb')),
        ]))
        elements.append(sum_table)
        elements.append(Spacer(1, 20))
        
        # Detailed Table
        elements.append(Paragraph("<b>VIP Customer Rankings Log</b>", styles['Heading3']))
        elements.append(Spacer(1, 8))
        
        table_data = [['Rank', 'Client Name', 'Email', 'Phone', 'Lifetime Value', 'Loyalty Balance']]
        for i, cust in enumerate(customers, 1):
            table_data.append([
                f"#{i}",
                cust.name,
                cust.email or 'N/A',
                cust.phone or 'N/A',
                f"Rs. {cust.lifetime_value:.2f}",
                f"{cust.loyalty_points} pts"
            ])
            
        t = Table(table_data, colWidths=[40, 120, 140, 90, 80, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), header_color),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, line_color),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
            ('FONTSIZE', (0,0), (-1,-1), 8),
        ]))
        elements.append(t)
        
    elif report_type == 'tax':
        invoices = Invoice.objects.filter(payment_status='Paid')
        total_subtotal = invoices.aggregate(Sum('subtotal'))['subtotal__sum'] or 0.00
        total_tax = invoices.aggregate(Sum('tax_amount'))['tax_amount__sum'] or 0.00
        total_gross = invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00
        
        cgst = total_tax / 2
        sgst = total_tax / 2
        
        # Summary
        summary_data = [
            [Paragraph("<b>Net Subtotal Base:</b>", style_normal), Paragraph(f"Rs. {total_subtotal:,.2f}", style_normal)],
            [Paragraph("<b>CGST collected (9% pool):</b>", style_normal), Paragraph(f"Rs. {cgst:,.2f}", style_normal)],
            [Paragraph("<b>SGST collected (9% pool):</b>", style_normal), Paragraph(f"Rs. {sgst:,.2f}", style_normal)],
            [Paragraph("<b>Gross Billing Assets:</b>", style_normal), Paragraph(f"Rs. {total_gross:,.2f}", style_normal)]
        ]
        sum_table = Table(summary_data, colWidths=[200, 200])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f3f4f6')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e5e7eb')),
        ]))
        elements.append(sum_table)
        elements.append(Spacer(1, 20))
        
        # Detailed Table
        elements.append(Paragraph("<b>Tax Audits Breakdown Log</b>", styles['Heading3']))
        elements.append(Spacer(1, 8))
        
        table_data = [['Invoice ID', 'Date', 'Transaction Total', 'Subtotal Base', 'Total GST Tax', 'CGST Portion', 'SGST Portion']]
        for inv in invoices:
            table_data.append([
                inv.invoice_number,
                inv.created_at.strftime('%Y-%m-%d'),
                f"Rs. {inv.total_amount:.2f}",
                f"Rs. {inv.subtotal:.2f}",
                f"Rs. {inv.tax_amount:.2f}",
                f"Rs. {inv.cgst:.2f}",
                f"Rs. {inv.sgst:.2f}"
            ])
            
        t = Table(table_data, colWidths=[100, 70, 90, 90, 70, 65, 65])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), header_color),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, line_color),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
            ('FONTSIZE', (0,0), (-1,-1), 8),
        ]))
        elements.append(t)
        
    # Build Document
    doc.build(elements)
    
    # Return File
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=False, filename=f"smartbill_{report_type}_report.pdf")
