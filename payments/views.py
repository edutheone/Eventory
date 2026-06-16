import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .mpesa import MpesaClient
from .models import Payment


@csrf_exempt
@require_POST
def initiate_payment(request):
    try:
        data = json.loads(request.body)
        event_id = data.get('event_id')
        phone = data.get('phone_number')
        amount = data.get('amount')
        quantity = data.get('quantity', 1)

        if not all([event_id, phone, amount]):
            return JsonResponse({'success': False, 'message': 'Missing required fields'}, status=400)

        client = MpesaClient()
        result = client.stk_push(
            phone_number=phone,
            amount=amount,
            account_ref=f"EVENT-{event_id}",
            description=f"Ticket purchase for event {event_id}",
        )

        if result.get('ResponseCode') == '0':
            Payment.objects.create(
                user=request.user if request.user.is_authenticated else None,
                event_id=event_id,
                phone_number=phone,
                amount=amount,
                quantity=quantity,
                merchant_request_id=result['MerchantRequestID'],
                checkout_request_id=result['CheckoutRequestID'],
            )
            return JsonResponse({
                'success': True,
                'message': 'Check your phone for the M-Pesa prompt.',
                'checkout_request_id': result['CheckoutRequestID']
            })
        else:
            return JsonResponse({
                'success': False,
                'message': result.get('errorMessage', 'Payment initiation failed.')
            })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def mpesa_callback(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        stk_callback = data['Body']['stkCallback']
        checkout_id = stk_callback['CheckoutRequestID']
        result_code = stk_callback['ResultCode']

        payment = Payment.objects.get(checkout_request_id=checkout_id)

        if result_code == 0:
            items = stk_callback['CallbackMetadata']['Item']
            meta = {item['Name']: item.get('Value') for item in items}
            payment.status = 'completed'
            payment.mpesa_receipt = meta.get('MpesaReceiptNumber', '')
        else:
            payment.status = 'failed'

        payment.save()

    except Payment.DoesNotExist:
        pass
    except Exception as e:
        print(f"Callback error: {e}")

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


def payment_status(request, checkout_id):
    try:
        payment = Payment.objects.get(checkout_request_id=checkout_id)
        return JsonResponse({
            'status': payment.status,
            'receipt': payment.mpesa_receipt
        })
    except Payment.DoesNotExist:
        return JsonResponse({'status': 'not_found'}, status=404)