from django.contrib import admin
from django.db.models.expressions import Ref
from .models import Item, OrderItem, Order, BillingAddress, Payment, Coupon, Refund


def make_refund_accepted(modeladmin, request, queryset):
    
    queryset.update(refund_requested=False, refund_granted=True)

make_refund_accepted.short_description = "Update refund status to granted"

class OrderAdmin(admin.ModelAdmin):
    list_display=[
                'user', 
                'ordered', 
                'being_delivered', 
                'received', 
                'refund_requested', 
                'refund_granted',
                'billing_address',
                'payment',
                'coupon'
    ]
    list_display_links = [
        'user',
        'billing_address',
        'payment',
        'coupon'
    ]
    search_fields = [
        'user__username',
        'ref_code'
    ]
    list_filter = [
                'being_delivered', 
                'received', 
                'refund_requested', 
                'refund_granted'
    ]
    actions = [
        make_refund_accepted
    ]

# Register your models here.
admin.site.register(Item)
admin.site.register(OrderItem)
admin.site.register(Order, OrderAdmin)
admin.site.register(BillingAddress)
admin.site.register(Payment)
admin.site.register(Coupon)
admin.site.register(Refund)