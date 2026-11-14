"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app
from service import talisman

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"


######################################################################
#  T E S T   C A S E S
######################################################################
class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        talisman.force_https = False
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Runs once before test suite"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []
        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(BASE_URL, json=account.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )
            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)
        return accounts

    ######################################################################
    #  A C C O U N T   T E S T   C A S E S
    ######################################################################

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should be healthy"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "OK")

    def test_create_account(self):
        """It should Create a new Account"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_account = response.get_json()
        self.assertEqual(new_account["name"], account.name)
        self.assertEqual(new_account["email"], account.email)
        self.assertEqual(new_account["address"], account.address)
        self.assertEqual(new_account["phone_number"], account.phone_number)
        self.assertEqual(new_account["date_joined"], str(account.date_joined))

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_read_an_account(self):
        """It should Read an existing Account"""
        account = self._create_accounts(1)[0]
        response = self.client.get(f"{BASE_URL}/{account.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), account.serialize())

    def test_account_not_found(self):
        """It should return 404 for a missing Account"""
        self.assertEqual(self.client.get(f"{BASE_URL}/99999").status_code, 404)

    def test_get_account_list(self):
        """It should List all Accounts"""
        accounts = self._create_accounts(3)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), len(accounts))

    def test_list_empty(self):
        """It should return an empty list when no Accounts exist"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_update_account(self):
        """It should Update and persist an Account"""
        account = self._create_accounts(1)[0]
        data = account.serialize()
        data["name"] = "Updated Customer"
        response = self.client.put(f"{BASE_URL}/{account.id}", json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["name"], data["name"])
        saved = self.client.get(f"{BASE_URL}/{account.id}").get_json()
        self.assertEqual(saved["name"], data["name"])
        self.assertEqual(saved["id"], account.id)

    def test_update_missing(self):
        """It should not Update a missing Account"""
        response = self.client.put(f"{BASE_URL}/99999",
                                   json=AccountFactory().serialize())
        self.assertEqual(response.status_code, 404)

    def test_update_bad_data(self):
        """It should reject an incomplete update"""
        account = self._create_accounts(1)[0]
        response = self.client.put(f"{BASE_URL}/{account.id}", json={})
        self.assertEqual(response.status_code, 400)

    def test_update_wrong_media(self):
        """It should reject a non-JSON update"""
        account = self._create_accounts(1)[0]
        response = self.client.put(f"{BASE_URL}/{account.id}", data="invalid")
        self.assertEqual(response.status_code, 415)

    def test_delete_account(self):
        """It should Delete an Account and return no content"""
        account = self._create_accounts(1)[0]
        response = self.client.delete(f"{BASE_URL}/{account.id}")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertEqual(self.client.get(f"{BASE_URL}/{account.id}").status_code,
                         404)

    def test_delete_missing(self):
        """It should keep DELETE idempotent for a missing Account"""
        self.assertEqual(self.client.delete(f"{BASE_URL}/99999").status_code, 204)

    def test_method_not_allowed(self):
        """It should reject unsupported HTTP methods"""
        self.assertEqual(self.client.put(BASE_URL).status_code, 405)

    def test_internal_server_error(self):
        """It should return JSON for unexpected database failures"""
        from unittest.mock import patch
        from werkzeug.exceptions import InternalServerError
        with patch('service.routes.Account.all',
                   side_effect=InternalServerError('Database unavailable')):
            response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()['error'], 'Internal Server Error')

    def test_create_without_optional_fields(self):
        """It should assign today's date and allow no phone number"""
        from datetime import date
        response = self.client.post(BASE_URL, json={
            'name': 'Sample Customer', 'email': 'sample@example.com',
            'address': 'Test address'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['date_joined'], date.today().isoformat())
        self.assertIsNone(response.get_json()['phone_number'])
        self.assertEqual(self.client.get(response.headers['Location']).status_code, 200)

    def test_security_headers(self):
        """It should return security headers for HTTPS requests"""
        response = self.client.get('/', environ_overrides={
            'wsgi.url_scheme': 'https'})
        self.assertEqual(response.status_code, 200)
        expected = {'X-Frame-Options': 'SAMEORIGIN',
                    'X-Content-Type-Options': 'nosniff',
                    'Content-Security-Policy': "default-src 'self'; object-src 'none'"}
        for key, value in expected.items():
            self.assertEqual(response.headers.get(key), value)
        self.assertIn('max-age=', response.headers['Strict-Transport-Security'])

    def test_cors_security(self):
        """It should return the course's public API CORS policy"""
        response = self.client.get('/')
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), '*')

    def test_https_redirect(self):
        """It should redirect insecure production requests to HTTPS"""
        talisman.force_https = True
        try:
            response = self.client.get('/')
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.headers['Location'].startswith('https://'))
        finally:
            talisman.force_https = False
