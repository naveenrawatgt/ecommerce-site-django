from typing import List
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic import ListView, DetailView, View
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Item, Order, OrderItem, BillingAddress, Payment, Coupon, Refund
from .forms import CheckoutForm, CouponForm, RefundRequestForm

import random
import string

# Create your views here.

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k = 20))

class HomeView(ListView):
    
    model = Item
    paginate_by = 10
    template_name = "home-page.html"

class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            orders = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'orders': orders
            }
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order.")
            return redirect("/")
        return render(self.request, "order-summary.html", context)


class ItemDetailView(DetailView):
    model = Item
    template_name = "product-page.html"

class CheckoutView(View):
    def get(self, *args, **kwargs):
        form = CheckoutForm()
        context = {
            'form': form,
            'couponform': CouponForm()
        }
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context["order"] = order
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order.")
            return redirect("/")
        return render(self.request, "checkout-page.html", context)
    
    def post(self, *args, **kwargs):
        form =CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():
                street_address=form.cleaned_data.get('street_address')
                apartment_address=form.cleaned_data.get('apartment_address')
                country=form.cleaned_data.get('country')
                zip_code=form.cleaned_data.get('zip_code')
                # TODO : Add functionality to use below options.
                # same_billing_address=form.cleaned_data.get('same_billing_address')
                # save_info=form.cleaned_data.get('save_info')
                payment_options=form.cleaned_data.get('payment_options')
                billing_address=BillingAddress(
                    user=self.request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    country=country,
                    zip_code=zip_code,
                    # same_billing_address=same_billing_address,
                    # save_info=save_info,
                    # payment_options=payment_options
                )
                billing_address.save()
                order.billing_address = billing_address
                order.save()
                if payment_options == 'S':
                    return redirect('core:payment', payment_options='stripe')
                elif payment_options == 'P':
                    return redirect('core:payment', payment_options='paypal')
                else:
                    messages.warning(self.request, "Invalid payment option selected.")        
            else:
                messages.warning(self.request, "Failed to validate.")
                return redirect('core:checkout')
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order.")
            return redirect('/')
        
class PaymentView(View):
    def get(self, *args, **kwargs):
        order=Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context={
                'order':order, 
                'couponform': CouponForm()
            }
            return render(self.request, "payment-page.html", context)
        else:
            messages.warning(self.request, "Please provide a billing address and then proceed.")
            return redirect("core:checkout")
    def post(self, *args, **kwargs):
        order=Order.objects.get(user=self.request.user, ordered=False)
        token=self.request.POST.get('stripeToken')
        amount=int(order.get_total())*100
        try:
            # Use Stripe's library to make requests...
            charge=stripe.Charge.create(
                amount=amount,
                currency="usd",
                source=token,
            )
                
            # Create Payment.
            payment=Payment()
            payment.stripe_charge_id=charge["id"]
            payment.user=self.request.user
            payment.amount=order.get_total()
            payment.save()

            order_item=order.items.all()
            order_item.update(ordered=True)
            for item in order_item:
                item.save()
            order.ordered=True
            order.payment=payment
            order.ref_code=create_ref_code()
            order.save()
            messages.success(self.request, "Your order was successful.")
            return redirect("/")
        except stripe.error.CardError as e:
            # Since it's a decline, stripe.error.CardError will be caught
            messages.warning(self.request, f"{e.user_message}")
            return redirect("/")
        except stripe.error.RateLimitError as e:
            # Too many requests made to the API too quickly
            messages.warning(self.request, f"{e.user_message}")
            return redirect("/")
        except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            messages.warning(self.request, f"{e.user_message}")
            return redirect("/")
        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
            messages.warning(self.request, f"{e.user_message}")
            return redirect("/")
        except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
            messages.warning(self.request, f"{e.user_message}")
            return redirect("/")
        except stripe.error.StripeError as e:
            # Display a very generic error to the user, and maybe send
            # yourself an email
            messages.warning(self.request, f"{e.user_message}")
            return redirect("/")
        except Exception as e:
            # send an email to you as admin.
            messages.warning(self.request, "Serious error occured. We have been notified.")
            return redirect("/")
        
@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # Check if order item is in the order.
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            messages.info(request, "The quantity is updated in your cart.")
            order_item.save()
        else:
            messages.info(request, "This item is added to your cart.")
            order.items.add(order_item)
    else:
        order = Order.objects.create(user=request.user, ordered_date = timezone.now())
        messages.info(request, "This item is added to your cart.")
        order.items.add(order_item)
    return redirect("core:order-summary")

@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)

    if order_qs.exists():
        order = order_qs[0]
        # Check if order item is in the order.
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(item=item, user=request.user, ordered=False)[0]
            messages.warning(request, "This item is removed from your cart.")
            order.items.remove(order_item)
            return redirect("core:order-summary")
        else:
            # Add a message here, order doesn't exist.
            messages.warning(request, "Item doesn't exists in your cart.")
            return redirect("core:product", slug=slug)
    else:
        # Add a message here, user doesn't have an order.
        messages.warning(request, "You do not have an active order.")
        return redirect("core:product", slug=slug)
    return redirect("core:product", slug=slug)

@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)

    if order_qs.exists():
        order = order_qs[0]
        # Check if order item is in the order.
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(item=item, user=request.user, ordered=False)[0]
            if order_item.quantity <= 1:
                remove_from_cart(request, order_item.item.slug)
            else:
                messages.warning(request, "This item quantity was updated.")
                order_item.quantity -= 1
                order_item.save()
        else:
            # Add a message here, order doesn't exist.
            messages.warning(request, "Item doesn't exists in your cart.")
    else:
        # Add a message here, user doesn't have an order.
        messages.warning(request, "You do not have an active order.")
    return redirect("core:order-summary")

def get_coupon(request, code):
    try:
        coupon=Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "You do not have a coupon to apply.")
        return redirect("core:checkout")    

class AddCoupon(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data["code"]
                order=Order.objects.get(user=self.request.user, ordered=False)
                order.coupon=get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Successfully added coupon.")
                return redirect("core:checkout")
            except ObjectDoesNotExist:
                messages.info(self.request, "You do not have an active order.")
                return redirect("/")

class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundRequestForm()
        context = {
            'form': form
        }

        return render(self.request, "request-refund-page.html", context)

    def post(self, *args, **kwargs):
        form = RefundRequestForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data['ref_code']
            message = form.cleaned_data['message']
            email = form.cleaned_data['email']

            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()
                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()
                messages.success(self.request, "Your request has been received.")
                return redirect("core:request-refund")
            except ObjectDoesNotExist:
                messages.warning(self.request, "Order doesn't exists.")
                return redirect("/")

            