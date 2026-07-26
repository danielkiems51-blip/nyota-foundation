import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class PayNexusService:
    """
    Service class to handle PayNexus API integration for M-Pesa STK Push payments.
    Uses the official PayNexus API at https://paynexus.co.ke/api/

    Authentication: X-API-Key header with your sk_... secret key from the PayNexus dashboard.

    STK Push endpoint: POST /api/mpesa/payment/initiate
    Status check:      GET  /api/payments/{reference}
    Status by checkout: POST /api/payments/status-by-checkout-id
    """

    PAYNEXUS_BASE_URL = 'https://paynexus.co.ke'
    STK_PUSH_PATH = '/api/mpesa/payment/initiate'
    PAYMENT_STATUS_PATH = '/api/payments'  # + /{reference}
    STATUS_BY_CHECKOUT_PATH = '/api/payments/status-by-checkout-id'

    def __init__(self):
        """Initialize the PayNexus Service with credentials from settings and validate."""
        # Base URL (defaults to official PayNexus)
        self.base_url = getattr(
            settings,
            'PAYNEXUS_API_URL',
            getattr(settings, 'SMARTPAYPESA_API_URL',
                    getattr(settings, 'TUMA_API_URL', self.PAYNEXUS_BASE_URL))
        ).rstrip('/')

        # Normalise legacy URLs that point to old domains or have /v1 suffix
        # to the canonical PayNexus base URL
        if '/v1' in self.base_url:
            # Strip /v1 suffix — the real PayNexus API doesn't use it
            self.base_url = self.base_url.rsplit('/v1', 1)[0].rstrip('/')

        self.shop_email = getattr(
            settings,
            'PAYNEXUS_SHOP_EMAIL',
            getattr(settings, 'SMARTPAYPESA_SHOP_EMAIL',
                    getattr(settings, 'TUMA_SHOP_EMAIL', None))
        )

        # PayNexus uses sk_... API keys via X-API-Key header
        self.api_key = (
            getattr(settings, 'PAYNEXUS_API_KEY', None)
            or getattr(settings, 'SMARTPAYPESA_API_KEY', None)
            or getattr(settings, 'TUMA_API_KEY', None)
        )

        self.callback_url = getattr(
            settings,
            'PAYNEXUS_CALLBACK_URL',
            getattr(settings, 'SMARTPAYPESA_CALLBACK_URL',
                    getattr(settings, 'TUMA_CALLBACK_URL', None))
        )

        # Validate required settings
        if not self.api_key:
            raise ValueError(
                "Missing critical PayNexus setting: PAYNEXUS_API_KEY. "
                "Get your sk_... key from https://paynexus.co.ke dashboard."
            )

        logger.info(f"PayNexusService initialized — base URL: {self.base_url}")

    def _get_headers(self):
        """Build request headers with PayNexus X-API-Key authentication."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": self.api_key,
            "User-Agent": "NyotaFund/1.0",
        }

    def initiate_stk_push(self, phone_number, amount, reference, description, callback_url=None):
        """
        Initiate an M-Pesa STK Push payment via PayNexus.

        Args:
            phone_number (str): Customer's M-Pesa phone number (07xxxxxxxx or 2547xxxxxxx)
            amount (float): Amount to charge (KES, minimum 1)
            reference (str): Unique business reference for the transaction
            description (str): Description shown to the customer
            callback_url (str, optional): Override callback URL for this request

        Returns:
            dict: {'success': True/False, 'data': {...} or 'message': '...'}
        """
        try:
            # Clean and normalize the phone number
            phone_number = self._normalize_phone(phone_number)

            # Build callback URL with reference for webhook reconciliation
            final_callback = callback_url or self.callback_url
            if final_callback and reference:
                separator = '&' if '?' in final_callback else '?'
                final_callback = f"{final_callback}{separator}reference={reference}"

            payload = {
                "amount": int(float(amount)),
                "phone": phone_number,
                "description": description or f"Payment - {reference}",
            }

            # Include callback_url in payload if available
            if final_callback:
                payload["callback_url"] = final_callback

            url = f"{self.base_url}{self.STK_PUSH_PATH}"

            logger.info(f"PayNexus STK Push -> {url}")
            print(f"[DEBUG] PayNexus STK Push -> URL: {url}, Payload: {payload}")

            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )

            # Parse JSON response
            try:
                response_data = response.json() if response.content else {}
            except ValueError:
                response_data = {"raw_response": response.text}

            if response.status_code in [200, 201]:
                logger.info(f"PayNexus STK Push success: {response_data}")
                return {
                    "success": True,
                    "data": response_data
                }
            else:
                error_msg = (
                    response_data.get('message')
                    or response_data.get('error')
                    or f"STK Push failed with status {response.status_code}"
                )
                logger.error(f"PayNexus STK Push error: {response.status_code} — {response_data}")
                return {
                    "success": False,
                    "message": error_msg,
                    "detail": response_data
                }

        except requests.exceptions.Timeout:
            logger.error("PayNexus API request timed out.")
            return {
                "success": False,
                "message": "Payment service request timed out. Please try again."
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"PayNexus connection error: {str(e)}")
            return {
                "success": False,
                "message": "Could not connect to PayNexus payment service. Please try again later."
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"PayNexus network error: {str(e)}")
            return {
                "success": False,
                "message": f"Network error connecting to payment service: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unhandled error in initiate_stk_push: {str(e)}")
            return {
                "success": False,
                "message": f"An unexpected error occurred: {str(e)}"
            }

    def check_payment_status(self, reference):
        """
        Check payment status by reference via PayNexus API.

        Args:
            reference (str): The payment reference to look up.

        Returns:
            dict: {'success': True/False, 'data': {...} or 'message': '...'}
        """
        try:
            url = f"{self.base_url}{self.PAYMENT_STATUS_PATH}/{reference}"

            logger.info(f"PayNexus status check -> {url}")
            response = requests.get(url, headers=self._get_headers(), timeout=15)

            try:
                response_data = response.json() if response.content else {}
            except ValueError:
                response_data = {"raw_response": response.text}

            if response.status_code in [200, 201]:
                return {"success": True, "data": response_data}
            else:
                return {
                    "success": False,
                    "message": response_data.get('message') or f"Status check failed ({response.status_code})",
                    "detail": response_data
                }
        except Exception as e:
            logger.error(f"PayNexus status check error: {str(e)}")
            return {"success": False, "message": str(e)}

    def check_status_by_checkout_id(self, checkout_request_id):
        """
        Check payment status by checkout request ID via PayNexus API.

        Args:
            checkout_request_id (str): The CheckoutRequestID from the STK push response.

        Returns:
            dict: {'success': True/False, 'data': {...} or 'message': '...'}
        """
        try:
            url = f"{self.base_url}{self.STATUS_BY_CHECKOUT_PATH}"
            payload = {"checkout_request_id": checkout_request_id}

            logger.info(f"PayNexus checkout status check -> {url}")
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)

            try:
                response_data = response.json() if response.content else {}
            except ValueError:
                response_data = {"raw_response": response.text}

            if response.status_code in [200, 201]:
                return {"success": True, "data": response_data}
            else:
                return {
                    "success": False,
                    "message": response_data.get('message') or f"Status check failed ({response.status_code})",
                    "detail": response_data
                }
        except Exception as e:
            logger.error(f"PayNexus checkout status check error: {str(e)}")
            return {"success": False, "message": str(e)}

    def _normalize_phone(self, phone):
        """Normalizes phone number to 2547xxxxxxx format (always 12 digits)."""
        # Keep only digits and strip leading zeros
        phone = ''.join(filter(str.isdigit, phone)).lstrip('0')

        # Strip any duplicate 254 country code prefixes until we have the 9-digit local number
        while phone.startswith('254') and len(phone) > 9:
            phone = phone[3:]

        # Re-add the 254 prefix once
        return '254' + phone


# Aliases for backward compatibility
SmartPayPesaService = PayNexusService
TumaService = PayNexusService
