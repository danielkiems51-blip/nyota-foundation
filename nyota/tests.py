from django.test import SimpleTestCase, override_settings
from unittest.mock import patch, MagicMock
import requests
from nyota.services import PayNexusService


PAYNEXUS_TEST_SETTINGS = {
    'PAYNEXUS_API_URL': 'https://paynexus.co.ke',
    'PAYNEXUS_API_KEY': 'sk_test_abc123xyz',
    'PAYNEXUS_SHOP_EMAIL': 'test@example.com',
    'PAYNEXUS_CALLBACK_URL': 'https://example.com/api/mpesa/callback/',
}


@override_settings(**PAYNEXUS_TEST_SETTINGS)
class PayNexusServiceTest(SimpleTestCase):
    def setUp(self):
        self.service = PayNexusService()

    def test_init_sets_correct_base_url(self):
        """Base URL should be https://paynexus.co.ke without /v1 suffix."""
        self.assertEqual(self.service.base_url, 'https://paynexus.co.ke')

    def test_init_strips_v1_from_legacy_url(self):
        """Legacy URLs with /v1 should be normalised to base URL."""
        with self.settings(PAYNEXUS_API_URL='https://paynexus.co.ke/v1'):
            svc = PayNexusService()
            self.assertEqual(svc.base_url, 'https://paynexus.co.ke')

    def test_init_raises_without_api_key(self):
        """Service should raise ValueError if no API key is configured."""
        with self.settings(PAYNEXUS_API_KEY='', SMARTPAYPESA_API_KEY=None, TUMA_API_KEY=None):
            with self.assertRaises(ValueError) as ctx:
                PayNexusService()
            self.assertIn('PAYNEXUS_API_KEY', str(ctx.exception))

    def test_headers_contain_x_api_key(self):
        """Request headers must use X-API-Key (not Bearer Authorization)."""
        headers = self.service._get_headers()
        self.assertEqual(headers['X-API-Key'], 'sk_test_abc123xyz')
        self.assertNotIn('Authorization', headers)

    def test_phone_normalization(self):
        """Test normalization of various phone formats to 2547xxxxxxx."""
        self.assertEqual(self.service._normalize_phone('0703137482'), '254703137482')
        self.assertEqual(self.service._normalize_phone('+254703137482'), '254703137482')
        self.assertEqual(self.service._normalize_phone('254703137482'), '254703137482')
        self.assertEqual(self.service._normalize_phone('703137482'), '254703137482')

    @patch('nyota.services.requests.post')
    def test_stk_push_success(self, mock_post):
        """STK push should return success when API responds with 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"success": true, "checkout_request_id": "ws_CO_123"}'
        mock_response.json.return_value = {"success": True, "checkout_request_id": "ws_CO_123"}
        mock_post.return_value = mock_response

        result = self.service.initiate_stk_push(
            phone_number='0703137482',
            amount=100,
            reference='TEST1234',
            description='Test Payment'
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['data']['checkout_request_id'], 'ws_CO_123')

        # Verify correct endpoint was called
        call_url = mock_post.call_args[0][0]
        self.assertEqual(call_url, 'https://paynexus.co.ke/api/mpesa/payment/initiate')

        # Verify X-API-Key header was sent
        call_headers = mock_post.call_args[1]['headers']
        self.assertEqual(call_headers['X-API-Key'], 'sk_test_abc123xyz')

    @patch('nyota.services.requests.post')
    def test_stk_push_unauthorized(self, mock_post):
        """STK push should return error message when API key is invalid."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.content = b'{"success": false, "error": "Unauthorized", "message": "API key required"}'
        mock_response.json.return_value = {"success": False, "error": "Unauthorized", "message": "API key required"}
        mock_post.return_value = mock_response

        result = self.service.initiate_stk_push(
            phone_number='0703137482',
            amount=100,
            reference='TEST1234',
            description='Test Payment'
        )

        self.assertFalse(result['success'])
        self.assertIn('API key', result['message'])

    @patch('nyota.services.requests.post')
    def test_stk_push_connection_error(self, mock_post):
        """STK push should return structured error on connection failure."""
        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Failed to establish a new connection: [Errno 113] No route to host"
        )

        result = self.service.initiate_stk_push(
            phone_number='0703137482',
            amount=100,
            reference='TEST1234',
            description='Test Payment'
        )

        self.assertFalse(result['success'])
        self.assertIn('connect', result['message'].lower())

    @patch('nyota.services.requests.post')
    def test_stk_push_timeout(self, mock_post):
        """STK push should return timeout message when request times out."""
        mock_post.side_effect = requests.exceptions.Timeout("Read timed out")

        result = self.service.initiate_stk_push(
            phone_number='0703137482',
            amount=100,
            reference='TEST1234',
            description='Test Payment'
        )

        self.assertFalse(result['success'])
        self.assertIn('timed out', result['message'].lower())

    @patch('nyota.services.requests.post')
    def test_stk_push_payload_format(self, mock_post):
        """Verify payload uses integer amount and normalized phone."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"success": true}'
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response

        self.service.initiate_stk_push(
            phone_number='0703137482',
            amount=100.50,
            reference='REF001',
            description='Test'
        )

        call_payload = mock_post.call_args[1]['json']
        self.assertEqual(call_payload['amount'], 100)  # integer
        self.assertEqual(call_payload['phone'], '254703137482')
        self.assertEqual(call_payload['description'], 'Test')
        self.assertIn('reference=REF001', call_payload['callback_url'])

    @patch('nyota.services.requests.get')
    def test_check_payment_status(self, mock_get):
        """Status check should call correct endpoint with X-API-Key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "completed"}'
        mock_response.json.return_value = {"status": "completed"}
        mock_get.return_value = mock_response

        result = self.service.check_payment_status('REF001')

        self.assertTrue(result['success'])
        call_url = mock_get.call_args[0][0]
        self.assertEqual(call_url, 'https://paynexus.co.ke/api/payments/REF001')
