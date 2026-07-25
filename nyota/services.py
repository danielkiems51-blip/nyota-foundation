import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class SmartPayPesaService:
    """
    Service class to handle SmartPayPesa API integration for M-Pesa STK Push payments.
    Ensures that all required environment variables are accessed safely and validated.
    """

    def __init__(self):
        """Initialize the SmartPayPesa Service with credentials from settings and validate."""
        default_url = getattr(settings, 'SMARTPAYPESA_API_URL', getattr(settings, 'TUMA_API_URL', 'https://api.smartpaypesa.com/v1'))
        # Fix legacy/invalid domain or path if passed in env
        if 'smartpaypesa.co.ke' in default_url:
            default_url = default_url.replace('smartpaypesa.co.ke', 'smartpaypesa.com')
        if not default_url.endswith('/v1') and 'smartpaypesa.com' in default_url:
            default_url = default_url.rstrip('/') + '/v1'
            
        self.api_url = default_url.rstrip('/')
        self.shop_email = getattr(settings, 'SMARTPAYPESA_SHOP_EMAIL', getattr(settings, 'TUMA_SHOP_EMAIL', None))
        self.api_key = getattr(settings, 'SMARTPAYPESA_API_KEY', getattr(settings, 'TUMA_API_KEY', None))
        self.callback_url = getattr(settings, 'SMARTPAYPESA_CALLBACK_URL', getattr(settings, 'TUMA_CALLBACK_URL', None))

        # Validate required settings
        missing = []
        if not self.shop_email and not self.api_key:
            missing.append('SMARTPAYPESA_API_KEY')

        if missing:
            raise ValueError(f"Missing critical SmartPayPesa settings: {', '.join(missing)}")

        logger.info(f"SmartPayPesaService initialized with API URL: {self.api_url}")

    def _get_access_token(self):
        """
        Authenticate with SmartPayPesa to retrieve JWT token if auth endpoint exists, or return API key.
        """
        if not self.api_key:
            return None

        url = f"{self.api_url}/auth/token"
        payload = {
            "email": self.shop_email,
            "api_key": self.api_key
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            logger.info(f"Authenticating with SmartPayPesa: {url}")
            response = requests.post(url, json=payload, headers=headers, timeout=5)
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                token = response_data.get('data', {}).get('token') or response_data.get('token')
                if token:
                    return token
        except Exception as e:
            logger.debug(f"Token endpoint check: {str(e)}")

        # SmartPayPesa uses API key directly as Bearer token
        return self.api_key

    def initiate_stk_push(self, phone_number, amount, reference, description, callback_url=None):
        """
        Initiate an STK Push payment via SmartPayPesa API.

        Args:
            phone_number (str): Customer's M-Pesa phone number (07xxxxxxxx or 2547xxxxxxx)
            amount (float): Amount to charge
            reference (str): Unique business reference for the transaction
            description (str): Description for the transaction
            callback_url (str, optional): Override callback URL

        Returns:
            dict: API response details
        """
        token = self._get_access_token()
        if not token:
            return {
                "success": False,
                "message": "Authentication with SmartPayPesa payment gateway failed."
            }

        try:
            # Clean and normalize the phone number
            phone_number = self._normalize_phone(phone_number)

            # Reconcile callback URL: append reference query parameter so we can identify it in the webhook
            final_callback = callback_url or self.callback_url
            if final_callback and reference:
                if '?' in final_callback:
                    final_callback = f"{final_callback}&reference={reference}"
                else:
                    final_callback = f"{final_callback}?reference={reference}"

            auth_header = f"Bearer {token}" if not str(token).startswith("Bearer ") else str(token)
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": auth_header,
                "X-API-Key": self.api_key or ""
            }

            payload = {
                "amount": float(amount),
                "phone": phone_number,
                "description": description,
                "callback_url": final_callback,
                "callbackurl": final_callback
            }

            # Primary and fallback endpoints for SmartPayPesa STK push
            candidate_urls = [
                f"{self.api_url}/stk/push",
                f"{self.api_url}/payment/stk-push",
                f"{self.api_url.rstrip('/v1')}/initiatestk"
            ]

            last_response = None
            for url in candidate_urls:
                logger.info(f"SmartPayPesa STK Push Request -> URL: {url}")
                print(f"[DEBUG] SmartPayPesa STK Push -> URL: {url}, Payload: {payload}")

                response = requests.post(url, headers=headers, json=payload, timeout=25)
                last_response = response

                if response.status_code in [200, 201]:
                    try:
                        response_data = response.json() if response.content else {}
                    except ValueError:
                        response_data = {"raw_response": response.text}
                    return {
                        "success": True,
                        "data": response_data
                    }
                elif response.status_code != 404:
                    # API endpoint responded (e.g. 400, 401, 500)
                    try:
                        response_data = response.json() if response.content else {}
                    except ValueError:
                        response_data = {"raw_response": response.text}
                    
                    logger.error(f"SmartPayPesa STK Push error: Status {response.status_code}, Detail: {response_data}")
                    return {
                        "success": False,
                        "message": response_data.get('error') or response_data.get('message') or f"STK Push failed with status code {response.status_code}",
                        "detail": response_data
                    }

            # If endpoints return 404
            resp_detail = last_response.text if last_response else "Endpoint not found"
            return {
                "success": False,
                "message": f"SmartPayPesa API endpoint returned status 404: {resp_detail}",
            }

        except requests.exceptions.Timeout:
            logger.error("SmartPayPesa API request timed out.")
            return {
                "success": False,
                "message": "Payment service API request timed out."
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during SmartPayPesa STK Push: {str(e)}")
            return {
                "success": False,
                "message": f"Network error connecting to payment service: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unhandled error in initiate_stk_push: {str(e)}")
            return {
                "success": False,
                "message": f"An unexpected server error occurred: {str(e)}"
            }



    def _normalize_phone(self, phone):
        """Normalizes phone number to 2547xxxxxxx format (always 12 digits)."""
        # Keep only digits and strip leading zeros
        phone = ''.join(filter(str.isdigit, phone)).lstrip('0')

        # Strip any duplicate 254 country code prefixes until we have the 9-digit local number
        while phone.startswith('254') and len(phone) > 9:
            phone = phone[3:]

        # Re-add the 254 prefix once
        return '254' + phone


# Alias for backward compatibility
TumaService = SmartPayPesaService

