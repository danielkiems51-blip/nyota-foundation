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
        self.api_url = getattr(settings, 'SMARTPAYPESA_API_URL', getattr(settings, 'TUMA_API_URL', 'https://api.smartpaypesa.co.ke')).rstrip('/')
        self.shop_email = getattr(settings, 'SMARTPAYPESA_SHOP_EMAIL', getattr(settings, 'TUMA_SHOP_EMAIL', None))
        self.api_key = getattr(settings, 'SMARTPAYPESA_API_KEY', getattr(settings, 'TUMA_API_KEY', None))
        self.callback_url = getattr(settings, 'SMARTPAYPESA_CALLBACK_URL', getattr(settings, 'TUMA_CALLBACK_URL', None))

        # Validate required settings
        missing = []
        if not self.shop_email: missing.append('SMARTPAYPESA_SHOP_EMAIL')
        if not self.api_key: missing.append('SMARTPAYPESA_API_KEY')

        if missing:
            raise ValueError(f"Missing critical SmartPayPesa settings: {', '.join(missing)}")

        logger.info("SmartPayPesaService initialized successfully")

    def _get_access_token(self):
        """
        Authenticate with SmartPayPesa and retrieve the JWT access token.
        """
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
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                token = response_data.get('data', {}).get('token') or response_data.get('token')
                if token:
                    return token
                else:
                    logger.error(f"SmartPayPesa token not found in response: {response_data}")
                    return None
            else:
                logger.error(f"SmartPayPesa auth failed: Status {response.status_code}, Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error authenticating with SmartPayPesa: {str(e)}")
            return None

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
            url = f"{self.api_url}/payment/stk-push"

            # Reconcile callback URL: append reference query parameter so we can identify it in the webhook
            final_callback = callback_url or self.callback_url
            if final_callback and reference:
                if '?' in final_callback:
                    final_callback = f"{final_callback}&reference={reference}"
                else:
                    final_callback = f"{final_callback}?reference={reference}"

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            }

            payload = {
                "amount": float(amount),
                "phone": phone_number,
                "description": description,
                "callback_url": final_callback
            }

            # Debug logging
            logger.info(f"SmartPayPesa STK Push Request -> URL: {url}")
            logger.info(f"SmartPayPesa STK Push Payload -> {payload}")
            print(f"[DEBUG] SmartPayPesa STK Push -> URL: {url}, Payload: {payload}")

            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            try:
                response_data = response.json() if response.content else {}
            except ValueError:
                response_data = {"raw_response": response.text}

            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "data": response_data
                }
            else:
                logger.error(f"SmartPayPesa STK Push failed: Status {response.status_code}, Detail: {response_data}")
                return {
                    "success": False,
                    "message": response_data.get('message', f"STK Push failed with status code {response.status_code}"),
                    "detail": response_data
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

