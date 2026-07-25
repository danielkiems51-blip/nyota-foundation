from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import SmartPayPesaService
from django.shortcuts import render, redirect
import json
import uuid
import logging

logger = logging.getLogger(__name__)

# Global cache for payment callbacks status updates
TRANSACTION_STATUSES = {}

def landing(request):
    limits = [
        {'amount': '5,000', 'charge': '100'},
        {'amount': '10,000', 'charge': '250'},
        {'amount': '15,000', 'charge': '500'},
        {'amount': '25,000', 'charge': '1,000'},
        {'amount': '35,000', 'charge': '1,500'},
        {'amount': '45,000', 'charge': '2,500'},
        {'amount': '55,000', 'charge': '3,500'},
        {'amount': '65,000', 'charge': '4,500'},
        {'amount': '75,000', 'charge': '5,500'}
    ]
    return render(request, 'nyota/landing.html', {'limits': limits})

@csrf_exempt
def initiate_payment(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            phone_number = data.get('phone_number')
            fee_amount = data.get('fee_amount') or data.get('amount')
            loan_amount = data.get('loan_amount', '0')
            full_name = data.get('full_name', 'User')
            county = data.get('county', 'Nairobi')
            reason = data.get('reason', 'General')
            
            # Remove commas from amount strings
            fee_amount = float(str(fee_amount).replace(',', ''))
            loan_amount = float(str(loan_amount).replace(',', ''))
            
            reference = str(uuid.uuid4())[:8].upper()
            description = f"Nyota Application - {reference}"
            
            # Store details in session since we don't have a database
            request.session['last_application'] = {
                'full_name': full_name,
                'amount': fee_amount,
                'reference': reference,
                'status': 'PENDING'
            }
            
            smartpaypesa = SmartPayPesaService()
            callback_url = request.build_absolute_uri('/api/mpesa/callback/')
            
            # Initialize global status as PENDING
            global TRANSACTION_STATUSES
            TRANSACTION_STATUSES[reference] = 'PENDING'
            
            result = smartpaypesa.initiate_stk_push(
                phone_number=phone_number,
                amount=fee_amount,
                reference=reference,
                description=description,
                callback_url=callback_url
            )
            
            if result.get('success'):
                # Store reference in session for tracking on status page
                request.session['current_tx_ref'] = reference
                # Update session status if we have a checkout ID
                application_data = request.session.get('last_application', {})
                data_resp = result.get('data', {})
                payment_id = data_resp.get('payment_id') or data_resp.get('CheckoutRequestID') or data_resp.get('data', {}).get('payment_id', '')
                application_data['checkout_request_id'] = payment_id
                request.session['last_application'] = application_data
            
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

def dashboard(request):
    """Placeholder dashboard for application overview."""
    return render(request, 'nyota/dashboard.html', {'message': 'Persistence disabled for application mode.'})

def offer_selection(request):
    """Enhanced offer selection page with dynamic slider logic."""
    limits = [
        {'amount': '5,000', 'charge': '100'},
        {'amount': '10,000', 'charge': '250'},
        {'amount': '15,000', 'charge': '500'},
        {'amount': '25,000', 'charge': '1,000'},
        {'amount': '35,000', 'charge': '1,500'},
        {'amount': '45,000', 'charge': '2,500'},
        {'amount': '55,000', 'charge': '3,500'},
        {'amount': '65,000', 'charge': '4,500'},
        {'amount': '75,000', 'charge': '5,500'}
    ]
    return render(request, 'nyota/offer_selection.html', {'limits': limits})

def payment_status(request):
    """Payment status page."""
    reference = request.GET.get('reference') or request.session.get('current_tx_ref')
    if not reference:
        return redirect('landing')
        
    # Use session data for display
    application = request.session.get('last_application', {})
    return render(request, 'nyota/payment_status.html', {'transaction': application})

def check_payment_status_api(request, reference):
    """API endpoint for polling payment status."""
    global TRANSACTION_STATUSES
    
    # Retrieve status from the global dictionary
    status = TRANSACTION_STATUSES.get(reference, 'PENDING')
    
    # Update user session if status changed
    application = request.session.get('last_application', {})
    if application and application.get('reference') == reference:
        if application.get('status') != status:
            application['status'] = status
            request.session['last_application'] = application
            request.session.modified = True
            
    return JsonResponse({
        'status': status,
        'app_status': 'PROCESSING' if status == 'SUCCESS' else 'PENDING'
    })

@csrf_exempt
def mpesa_callback(request):
    """
    Handle M-Pesa payment callback from SmartPayPesa.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            logger_data = json.dumps(data, indent=2)
            print(f"Callback received: {logger_data}")
            logger.info(f"SmartPayPesa Callback received: {logger_data}")
            
            # Reconcile reference
            # Try to read reference from query parameters first (which we appended in SmartPayPesaService)
            reference = request.GET.get('reference')
            
            # Fallback to SmartPayPesa payload keys if not in query parameters
            if not reference:
                reference = data.get('merchant_request_id') or data.get('reference') or data.get('external_reference') or data.get('transaction_id')
            
            # Reconcile status
            status = data.get('status')
            status_code = data.get('status_code')
            
            is_success = False
            if status and str(status).upper() in ['COMPLETED', 'SUCCESS']:
                is_success = True
            elif status_code and str(status_code) == "200":
                is_success = True
            
            if reference:
                global TRANSACTION_STATUSES
                status_msg = "SUCCESS" if is_success else "FAILED"
                TRANSACTION_STATUSES[reference] = status_msg
                logger.info(f"Application callback for ref {reference}: {status_msg}")
            else:
                logger.warning("Callback received but no reference could be parsed")
            
            return JsonResponse({'status': 'Received'})
        except Exception as e:
            logger.error(f"Callback error: {str(e)}")
            return JsonResponse({'status': 'Error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'Method not allowed'}, status=405)

