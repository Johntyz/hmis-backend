"""
Base test case for Users module tests.

The Users module is self-contained — no FK dependencies
on patients, appointments, or consultations.

Fixtures built in setUp():
    self.admin          → CustomUser(is_superuser=True)
    self.doctor         → CustomUser(role='doctor')
    self.receptionist   → CustomUser(role='receptionist')

URL constants:
    LOGIN_URL, LOGOUT_URL, ME_URL, CHANGE_PASSWORD_URL
    STAFF_URL, staff_url(pk), staff_doctors_url

Notes:
    - Passwords follow Django's validators (min 8 chars, not all numeric)
    - Auth helper obtains a real JWT token via the login endpoint
    - Staff management endpoints are admin-only (IsAdmin = is_superuser)
"""

from rest_framework.test import APITestCase, APIClient
from apps.users.models import CustomUser


class UserTestBase(APITestCase):

    PASSWORD = 'StrongPass123!'
    NEW_PASSWORD = 'NewStrongPass456!'

    LOGIN_URL = '/api/users/auth/login/'
    LOGOUT_URL = '/api/users/auth/logout/'
    ME_URL = '/api/users/auth/me/'
    CHANGE_PASSWORD_URL = '/api/users/auth/change-password/'
    STAFF_URL = '/api/users/staff/'

    def staff_url(self, pk):
        return f'{self.STAFF_URL}{pk}/'

    # ------------------------------------------------------------------
    # setUp
    # ------------------------------------------------------------------

    def setUp(self):
        self.client = APIClient()

        self.admin = self._make_user(
            username='admin_one',
            role='admin',
            first_name='Super',
            last_name='Admin',
            is_superuser=True,
            is_staff=True,
        )
        self.doctor = self._make_user(
            username='doctor_one',
            role='doctor',
            first_name='James',
            last_name='Mwangi',
            email='doctor@hmis.test',
            phone='0700000001',
        )
        self.receptionist = self._make_user(
            username='receptionist_one',
            role='receptionist',
            first_name='Grace',
            last_name='Otieno',
            email='receptionist@hmis.test',
            phone='0700000002',
        )

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    def _make_user(self, username, role, first_name='', last_name='',
                   email=None, phone=None, is_superuser=False, is_staff=False):
        return CustomUser.objects.create_user(
            username=username,
            password=self.PASSWORD,
            role=role,
            first_name=first_name,
            last_name=last_name,
            email=email or f'{username}@hmis.test',
            phone_number=phone,
            is_superuser=is_superuser,
            is_staff=is_staff,
        )

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def auth(self, user):
        """Obtains JWT token and sets it on the client."""
        response = self.client.post(
            self.LOGIN_URL,
            {'username': user.username, 'password': self.PASSWORD},
            format='json',
        )
        self.assertEqual(
            response.status_code, 200,
            msg=f"Auth failed for '{user.username}': {response.data}"
        )
        token = response.data.get('access')
        self.assertIsNotNone(token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return response.data  # return full login response for login-specific tests

    def clear_auth(self):
        self.client.credentials()