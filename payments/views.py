from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView

from borrowing.models import Fine
from .models import Payment
from .services import create_payment_for_fine, process_payment, get_payment_status


class PayFineView(LoginRequiredMixin, View):
    """Endpoint to initiate payment for a fine.

    POST parameters:
    - fine_id (path or POST data)
    - amount (optional)
    - payment_method (optional)

    This view creates a Payment record and processes it via the services
    layer. On success redirects to payment history or fine list.
    """

    def post(self, request, pk=None):
        user = request.user
        # pk may be provided via URL; otherwise expect fine_id in POST
        fine_id = pk or request.POST.get("fine_id")
        if not fine_id:
            raise Http404("Fine id required")

        fine = get_object_or_404(Fine, pk=fine_id)

        # Only the fine owner or admins may pay
        if fine.user != user and not (user.is_superuser or getattr(user, "role", None) == "ADMIN"):
            raise Http404("Not authorized")

        if fine.is_paid:
            messages.info(request, "This fine is already paid.")
            return redirect(reverse_lazy("borrowing:fine_list"))

        amount = request.POST.get("amount")
        payment_method = request.POST.get("payment_method", "default")

        # Create payment record
        payment = create_payment_for_fine(fine, user, amount=amount)

        # Process payment (synchronous simple gateway)
        try:
            result = process_payment(payment, payment_method=payment_method)
        except Exception:
            messages.error(request, "Payment processing failed. Please try again.", extra_tags="danger")
            return redirect(reverse_lazy("borrowing:fine_list"))

        if result.get("success"):
            messages.success(request, "Payment successful. Thank you.")
        else:
            messages.error(request, f"Payment failed: {result.get('message', 'Unknown')}", extra_tags="danger")

        return redirect(reverse_lazy("payments:payment_history"))


class PaymentHistoryView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = "payments/payment_history.html"
    context_object_name = "payments"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        # Admins can see all payments
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            return Payment.objects.select_related("fine", "user").all()
        return Payment.objects.select_related("fine").filter(user=user)


class PaymentStatusView(LoginRequiredMixin, View):
    """Return JSON status for a payment.

    URL param: payment_pk
    """

    def get(self, request, payment_pk):
        payment = get_object_or_404(Payment, pk=payment_pk)

        # Only owner or admin
        user = request.user
        if payment.user != user and not (user.is_superuser or getattr(user, "role", None) == "ADMIN"):
            return JsonResponse({"error": "not_authorized"}, status=403)

        status_info = get_payment_status(payment)
        return JsonResponse({"payment_id": payment.pk, "status": status_info})
