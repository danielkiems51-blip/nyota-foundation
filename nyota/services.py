import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class TumaService:
    """
    Service class to handle Tuma API integration for M-Pesa STK Push payments.
    Ensures that all required environment variables are accessed safely and validated.
    """

    def __init__(self):
        """Initialize the Tuma Service with credentials from settings and validate."""
        self.api_url = getattr(settings, 'TUMA_API_URL', 'https://api.tuma.co.ke').rstrip('/')
        self.shop_email = getattr(settings, 'TUMA_SHOP_EMAIL', None)
        self.api_key = getattr(settings, 'TUMA_API_KEY', None)
        self.callback_url = getattr(settings, 'TUMA_CALLBACK_URL', None)

        # Validate required settings
        missing = []
        if not self.shop_email: missing.append('TUMA_SHOP_EMAIL')
        if not self.api_key: missing.append('TUMA_API_KEY')

        if missing:
            raise ValueError(f"Missing critical Tuma settings: {', '.join(missing)}")

        logger.info("TumaService initialized successfully")

    def _get_access_token(self):
        """
        Authenticate with Tuma and retrieve the JWT access token.
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
            logger.info(f"Authenticating with Tuma: {url}")
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                token = response_data.get('data', {}).get('token') or response_data.get('token')
                if token:
                    return token
                else:
                    logger.error(f"Tuma token not found in response: {response_data}")
                    return None
            else:
                logger.error(f"Tuma auth failed: Status {response.status_code}, Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error authenticating with Tuma: {str(e)}")
            return None

    def initiate_stk_push(self, phone_number, amount, reference, description, callback_url=None):
        """
        Initiate an STK Push payment via Tuma API.

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
                "message": "Authentication with Tuma payment gateway failed."
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
            logger.info(f"Tuma STK Push Request -> URL: {url}")
            logger.info(f"Tuma STK Push Payload -> {payload}")
            print(f"[DEBUG] Tuma STK Push -> URL: {url}, Payload: {payload}")

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
                logger.error(f"Tuma STK Push failed: Status {response.status_code}, Detail: {response_data}")
                return {
                    "success": False,
                    "message": response_data.get('message', f"STK Push failed with status code {response.status_code}"),
                    "detail": response_data
                }

        except requests.exceptions.Timeout:
            logger.error("Tuma API request timed out.")
            return {
                "success": False,
                "message": "Payment service API request timed out."
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Tuma STK Push: {str(e)}")
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
        """Normalizes phone number to 2547xxxxxxx format."""
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone)).lstrip("0")

        # Convert to start with 254
        if phone.startswith("0"):
            phone = "254" + phone[1:]
        elif not phone.startswith("254"):
            phone = "254" + phone

        return phone
