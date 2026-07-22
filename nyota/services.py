import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class PaynexusService:
    """
    Service class to handle PayNexus API integration for M-Pesa STK Push payments.
    Ensures that all required environment variables are accessed safely and validated.
    """

    def __init__(self):
        """Initialize the PayNexus Service with credentials from settings and validate."""
        # Use getattr with None default to prevent an AttributeError if the key is missing
        # in the settings module (the cause of the 500 error crash).
        self.api_url = getattr(settings, 'PAYNEXUS_API_URL', None)
        self.api_key = getattr(settings, 'PAYNEXUS_API_KEY', None)
        self.callback_url = getattr(settings, 'PAYNEXUS_CALLBACK_URL', None)

        # Validate required settings
        missing = []
        if not self.api_url: missing.append('PAYNEXUS_API_URL')
        if not self.api_key: missing.append('PAYNEXUS_API_KEY')

        if missing:
            raise ValueError(f"Missing critical PayNexus settings: {', '.join(missing)}")

        logger.info("PaynexusService initialized successfully")

    def initiate_stk_push(self, phone_number, amount, reference, description, callback_url=None):
        """
        Initiate an STK Push payment via PayNexus API.

        Args:
            phone_number (str): Customer's M-Pesa phone number (07xxxxxxxx or 2547xxxxxxx)
            amount (float): Amount to charge
            reference (str): Unique business reference for the transaction
            description (str): Description for the transaction
            callback_url (str, optional): Override callback URL

        Returns:
            dict: API response details
        """
        # Ensure the client is fully initialized before attempting an API call
        if not all([self.api_url, self.api_key]):
            return {
                "success": False,
                "message": "PayNexus service not configured correctly. Check initialization logs."
            }

        try:
            # Clean and normalize the phone number
            phone_number = self._normalize_phone(phone_number)

            url = self.api_url

            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            }

            payload = {
                "amount": int(float(amount)),
                "phone": phone_number,
                "description": description,
            }

            # Include callback_url if provided
            if callback_url or self.callback_url:
                payload["callback_url"] = callback_url or self.callback_url

            # Include external_reference if provided
            if reference:
                payload["external_reference"] = reference

            # Debug logging to diagnose errors from PayNexus
            logger.info(f"PayNexus STK Push Request -> URL: {url}")
            logger.info(f"PayNexus STK Push Payload -> {payload}")
            print(f"[DEBUG] PayNexus STK Push -> URL: {url}, Payload: {payload}")

            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                # Log the detailed API error response
                error_detail = response.json() if response.content else response.text
                logger.error(f"PayNexus STK Push failed: Status {response.status_code}, Detail: {error_detail}")
                return {
                    "success": False,
                    "message": f"STK Push failed with status code {response.status_code}",
                    "detail": error_detail
                }

        except requests.exceptions.Timeout:
            logger.error("PayNexus API request timed out.")
            return {
                "success": False,
                "message": "Payment service API request timed out."
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during PayNexus STK Push: {str(e)}")
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

    def query_transaction_status(self, transaction_id):
        """
        Query the status of a transaction from PayNexus API.

        Args:
            transaction_id (str): The PayNexus transaction ID

        Returns:
            dict: Transaction status information
        """
        try:
            # Derive the status URL from the base API URL
            base_url = self.api_url.rsplit('/', 1)[0] if '/initiate' in self.api_url else self.api_url.rstrip('/')
            url = f"{base_url}/status"

            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            }

            # Pass transaction_id as the reference query parameter
            params = {"reference": transaction_id}
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to query transaction: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Error querying transaction status: {str(e)}")
            return {
                "success": False,
                "message": str(e)
            }
