from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .webhooks import WebhookSignatureError, handle_webhook


@csrf_exempt
@require_POST
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    try:
        handle_webhook(request.body, request.headers.get("Stripe-Signature", ""))
    except WebhookSignatureError:
        return HttpResponse("Invalid signature", status=400)
    return HttpResponse("ok")
