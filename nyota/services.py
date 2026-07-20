import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class PayheroService:
    """
    Service class to handle Payhero API integration for M-Pesa STK Push payments.
    Ensures that all required environment variables are accessed safely and validated.
    """

    def __init__(self):
        """Initialize the Payhero Service with credentials from settings and validate."""
        # Use getattr with None default to prevent an AttributeError if the key is missing
        # in the settings module (the cause of the 500 error crash).
        self.api_url = getattr(settings, 'PAYHERO_API_URL', None)
        self.channel_id = getattr(settings, 'PAYHERO_CHANNEL_ID', None)
        self.username = getattr(settings, 'PAYHERO_API_USERNAME', None)
        self.password = getattr(settings, 'PAYHERO_API_PASSWORD', None)
        self.callback_url = getattr(settings, 'PAYHERO_CALLBACK_URL', None)
        
        raw_token = getattr(settings, 'BASIC_AUTH_TOKEN', None)
        
        # Clean the basic auth token: remove leading/trailing whitespace, and any single/double quotes.
        # FIX: Corrected the quote syntax to prevent the SyntaxError.
        self.basic_auth_token = raw_token.strip().strip('"').strip("'") if raw_token else None

        # 1. Validate Core API URL and Channel ID
        missing_core = []
        if not self.api_url: missing_core.append('PAYHERO_API_URL')
        if not self.channel_id: missing_core.append('PAYHERO_CHANNEL_ID')

        if missing_core:
            raise ValueError(f"Missing critical Payhero settings: {', '.join(missing_core)}")

        # 2. Validate Authentication method
        has_token = bool(self.basic_auth_token)
        has_credentials = bool(self.username and self.password)
        
        if not (has_token or has_credentials):
            raise ValueError(
                "Missing Payhero authentication. Provide either BASIC_AUTH_TOKEN "
                "or both PAYHERO_API_USERNAME and PAYHERO_API_PASSWORD"
            )

        auth_method = "Basic Auth Token" if has_token else "Username/Password"
        logger.info(f"PayheroService initialized successfully using {auth_method}")

    def initiate_stk_push(self, phone_number, amount, reference, description, callback_url=None):
        """
        Initiate an STK Push payment via Payhero API.

        Args:
            phone_number (str): Customer's M-Pesa phone number (2547xxxxxxx)
            amount (float): Amount to charge
            reference (str): Unique business reference for the transaction
            description (str): Description for the transaction

        Returns:
            dict: API response details
        """
        # Ensure the client is fully initialized before attempting an API call
        if not all([self.api_url, self.channel_id]) or not (self.basic_auth_token or (self.username and self.password)):
            return {
                "success": False,
                "message": "Payhero service not configured correctly. Check initialization logs."
            }
            
        try:
            # Clean and normalize the phone number
            phone_number = self._normalize_phone(phone_number)

            # Ensure the URL points to the STK Push endpoint
            url = self.api_url
            if not url.endswith("/initiate-stk-push"):
                url = f"{url.rstrip('/')}/initiate-stk-push"
            
            headers = {
                "Content-Type": "application/json",
            }

            auth = None
            if self.basic_auth_token:
                headers["Authorization"] = self.basic_auth_token if self.basic_auth_token.startswith("Basic ") else f"Basic {self.basic_auth_token}"
            else:
                auth = (self.username, self.password)

            payload = {
                "amount": int(float(amount)),
                "phone_number": phone_number,
                "channel_id": int(self.channel_id) if str(self.channel_id).isdigit() else self.channel_id,
                "provider": "m-pesa",
                "external_reference": reference,
                "callback_url": callback_url or self.callback_url,
            }

            response = requests.post(url, headers=headers, json=payload, auth=auth, timeout=30)
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                # Log the detailed API error response
                error_detail = response.json() if response.content else response.text
                logger.error(f"Payhero STK Push failed: Status {response.status_code}, Detail: {error_detail}")
                return {
                    "success": False,
                    "message": f"STK Push failed with status code {response.status_code}",
                    "detail": error_detail
                }

        except requests.exceptions.Timeout:
            logger.error("Payhero API request timed out.")
            return {
                "success": False,
                "message": "Payment service API request timed out."
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Payhero STK Push: {str(e)}")
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
        Query the status of a transaction from Payhero API.

        Args:
            transaction_id (str): The Payhero transaction ID

        Returns:
            dict: Transaction status information
        """
        try:
            # Derive the base URL by removing /payments if present, and append /transaction-status
            base_url = self.api_url.split('/payments')[0]
            url = f"{base_url.rstrip('/')}/transaction-status"
            
            headers = {
                "Content-Type": "application/json",
            }

            auth = None
            if self.basic_auth_token:
                headers["Authorization"] = self.basic_auth_token if self.basic_auth_token.startswith("Basic ") else f"Basic {self.basic_auth_token}"
            else:
                auth = (self.username, self.password)

            # Pass transaction_id as the reference query parameter
            params = {"reference": transaction_id}
            response = requests.get(url, headers=headers, auth=auth, params=params, timeout=30)

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
