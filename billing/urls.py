from django.urls import path
from django.shortcuts import render
from . import views

urlpatterns = [
    # Dashboard Endpoint
    path('', views.dashboard_view, name='dashboard'),
    
    # Products Endpoints
    path('products/', views.product_list_view, name='products'),
    path('products/save/', views.save_product_view, name='save_product'),
    path('products/adjust/', views.adjust_stock_view, name='adjust_stock'),
    
    # Customers Endpoints
    path('customers/', views.customer_list_view, name='customers'),
    path('customers/save/', views.save_customer_view, name='save_customer'),
    
    # Transactional Endpoints
    path('invoice/create/', views.create_invoice_view, name='create_invoice'),
    
    # Reports Endpoints
    path('reports/', lambda r: render(r, 'reports.html', {'active_page': 'reports'}), name='reports'),
    path('reports/generate/', views.generate_pdf_report_view, name='generate_pdf_report'),
    path('invoice/<int:invoice_id>/pdf/', views.generate_invoice_pdf_view, name='generate_invoice_pdf'),
]
