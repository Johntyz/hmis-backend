"""
API tests for the Users module.

Covers all endpoints:
    TestLoginView           → POST /auth/login/
    TestLogoutView          → POST /auth/logout/
    TestMeView              → GET/PATCH /auth/me/
    TestChangePasswordView  → POST /auth/change-password/
    TestStaffList           → GET /staff/
    TestStaffRetrieve       → GET /staff/{id}/
    TestStaffCreate         → POST /staff/
    TestStaffUpdate         → PATCH /staff/{id}/
    TestStaffDeactivate     → DELETE /staff/{id}/
"""

from django.utils import timezone
from rest_framework import status
from .base import UserTestBase


# ==========================================================================
# LOGIN
# ==========================================================================

class TestLoginView(UserTestBase):

    def test_valid_credentials_return_tokens(self):
        response = self.client.post(self.LOGIN_URL, {
            'username': 'doctor_one',
            'password': self.PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_response_includes_user_info(self):
        response = self.client.post(self.LOGIN_URL, {
            'username': 'doctor_one',
            'password': self.PASSWORD,
        }, format='json')
        user_data = response.data['user']
        self.assertIn('id', user_data)
        self.assertIn('username', user_data)
        self.assertIn('role', user_data)
        self.assertIn('full_name', user_data)
        self.assertNotIn('password', user_data)

    def test_wrong_password_returns_401(self):
        response = self.client.post(self.LOGIN_URL, {
            'username': 'doctor_one',
            'password': 'WrongPassword!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_user_returns_401(self):
        response = self.client.post(self.LOGIN_URL, {
            'username': 'ghost_user',
            'password': self.PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_deactivated_user_cannot_login(self):
        self.doctor.is_active = False
        self.doctor.save()

        response = self.client.post(self.LOGIN_URL, {
            'username': 'doctor_one',
            'password': self.PASSWORD,
        }, format='json')
        # Django's authenticate() returns None for inactive users,
        # so the view hits the 401 branch before the 403 branch.
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_fields_return_400(self):
        response = self.client.post(self.LOGIN_URL, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_login_returns_admin_role(self):
        response = self.client.post(self.LOGIN_URL, {
            'username': 'admin_one',
            'password': self.PASSWORD,
        }, format='json')
        self.assertEqual(response.data['user']['role'], 'admin')


# ==========================================================================
# LOGOUT
# ==========================================================================

class TestLogoutView(UserTestBase):

    def test_valid_refresh_token_logs_out(self):
        login_data = self.auth(self.doctor)
        refresh_token = login_data['refresh']

        response = self.client.post(
            self.LOGOUT_URL,
            {'refresh': refresh_token},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_refresh_token_returns_400(self):
        self.auth(self.doctor)
        response = self.client.post(self.LOGOUT_URL, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_refresh_token_returns_400(self):
        self.auth(self.doctor)
        response = self.client.post(
            self.LOGOUT_URL,
            {'refresh': 'not.a.valid.token'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_logout(self):
        self.clear_auth()
        response = self.client.post(
            self.LOGOUT_URL,
            {'refresh': 'anything'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==========================================================================
# ME VIEW
# ==========================================================================

class TestMeView(UserTestBase):

    def test_authenticated_user_can_get_own_profile(self):
        self.auth(self.doctor)
        response = self.client.get(self.ME_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'doctor_one')

    def test_profile_response_never_exposes_password(self):
        self.auth(self.doctor)
        response = self.client.get(self.ME_URL)
        self.assertNotIn('password', response.data)

    def test_unauthenticated_cannot_get_profile(self):
        self.clear_auth()
        response = self.client.get(self.ME_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_update_own_profile(self):
        self.auth(self.doctor)
        response = self.client.patch(self.ME_URL, {
            'first_name': 'Updated',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Updated')

    def test_user_cannot_self_assign_admin_role(self):
        self.auth(self.doctor)
        response = self.client.patch(self.ME_URL, {
            'role': 'admin',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_update_to_duplicate_email(self):
        self.auth(self.doctor)
        response = self.client.patch(self.ME_URL, {
            'email': 'receptionist@hmis.test',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_update_profile(self):
        self.clear_auth()
        response = self.client.patch(self.ME_URL, {'first_name': 'Hacker'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==========================================================================
# CHANGE PASSWORD
# ==========================================================================

class TestChangePasswordView(UserTestBase):

    def test_correct_old_password_allows_change(self):
        self.auth(self.doctor)
        response = self.client.post(self.CHANGE_PASSWORD_URL, {
            'old_password': self.PASSWORD,
            'new_password': self.NEW_PASSWORD,
            'confirm_new_password': self.NEW_PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_wrong_old_password_returns_400(self):
        self.auth(self.doctor)
        response = self.client.post(self.CHANGE_PASSWORD_URL, {
            'old_password': 'WrongPassword!',
            'new_password': self.NEW_PASSWORD,
            'confirm_new_password': self.NEW_PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mismatched_new_passwords_return_400(self):
        self.auth(self.doctor)
        response = self.client.post(self.CHANGE_PASSWORD_URL, {
            'old_password': self.PASSWORD,
            'new_password': self.NEW_PASSWORD,
            'confirm_new_password': 'DifferentPassword999!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_password_returns_400(self):
        self.auth(self.doctor)
        response = self.client.post(self.CHANGE_PASSWORD_URL, {
            'old_password': self.PASSWORD,
            'new_password': self.PASSWORD,
            'confirm_new_password': self.PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_change_password(self):
        self.clear_auth()
        response = self.client.post(self.CHANGE_PASSWORD_URL, {
            'old_password': self.PASSWORD,
            'new_password': self.NEW_PASSWORD,
            'confirm_new_password': self.NEW_PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_after_change_old_password_no_longer_works(self):
        """Token from old password should be invalidated on next login."""
        self.auth(self.doctor)
        self.client.post(self.CHANGE_PASSWORD_URL, {
            'old_password': self.PASSWORD,
            'new_password': self.NEW_PASSWORD,
            'confirm_new_password': self.NEW_PASSWORD,
        }, format='json')

        # Try logging in with old password
        self.clear_auth()
        response = self.client.post(self.LOGIN_URL, {
            'username': 'doctor_one',
            'password': self.PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==========================================================================
# STAFF LIST
# ==========================================================================

class TestStaffList(UserTestBase):

    def test_admin_can_list_staff(self):
        self.auth(self.admin)
        response = self.client.get(self.STAFF_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_excludes_superusers(self):
        self.auth(self.admin)
        response = self.client.get(self.STAFF_URL)
        usernames = [u['username'] for u in response.data]
        self.assertNotIn('admin_one', usernames)
        self.assertIn('doctor_one', usernames)
        self.assertIn('receptionist_one', usernames)

    def test_list_excludes_soft_deleted_staff(self):
        self.doctor.deleted_at = timezone.now()
        self.doctor.save()

        self.auth(self.admin)
        response = self.client.get(self.STAFF_URL)
        usernames = [u['username'] for u in response.data]
        self.assertNotIn('doctor_one', usernames)

    def test_response_never_exposes_password(self):
        self.auth(self.admin)
        response = self.client.get(self.STAFF_URL)
        for user in response.data:
            self.assertNotIn('password', user)

    def test_doctor_cannot_list_staff(self):
        self.auth(self.doctor)
        response = self.client.get(self.STAFF_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_receptionist_cannot_list_staff(self):
        self.auth(self.receptionist)
        response = self.client.get(self.STAFF_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_list_staff(self):
        self.clear_auth()
        response = self.client.get(self.STAFF_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==========================================================================
# STAFF RETRIEVE
# ==========================================================================

class TestStaffRetrieve(UserTestBase):

    def test_admin_can_retrieve_any_staff_member(self):
        self.auth(self.admin)
        response = self.client.get(self.staff_url(self.doctor.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'doctor_one')

    def test_retrieve_nonexistent_returns_404(self):
        self.auth(self.admin)
        response = self.client.get(self.staff_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_soft_deleted_returns_404(self):
        self.doctor.deleted_at = timezone.now()
        self.doctor.save()

        self.auth(self.admin)
        response = self.client.get(self.staff_url(self.doctor.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_doctor_cannot_retrieve_staff(self):
        self.auth(self.doctor)
        response = self.client.get(self.staff_url(self.receptionist.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ==========================================================================
# STAFF CREATE
# ==========================================================================

class TestStaffCreate(UserTestBase):

    def _create_payload(self, username='new_staff', role='doctor',
                        email='newstaff@hmis.test'):
        return {
            'username': username,
            'email': email,
            'first_name': 'New',
            'last_name': 'Staff',
            'role': role,
            'password': self.PASSWORD,
            'confirm_password': self.PASSWORD,
        }

    def test_admin_can_create_doctor(self):
        self.auth(self.admin)
        response = self.client.post(
            self.STAFF_URL, self._create_payload(), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'doctor')

    def test_admin_can_create_receptionist(self):
        self.auth(self.admin)
        response = self.client.post(
            self.STAFF_URL,
            self._create_payload(username='new_recept', role='receptionist',
                                 email='newrecept@hmis.test'),
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'receptionist')

    def test_cannot_create_admin_via_api(self):
        self.auth(self.admin)
        response = self.client.post(
            self.STAFF_URL,
            self._create_payload(role='admin'),
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mismatched_passwords_rejected(self):
        self.auth(self.admin)
        payload = self._create_payload()
        payload['confirm_password'] = 'DifferentPass999!'
        response = self.client.post(self.STAFF_URL, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_email_rejected(self):
        self.auth(self.admin)
        payload = self._create_payload(email='doctor@hmis.test')
        response = self.client.post(self.STAFF_URL, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_username_rejected(self):
        self.auth(self.admin)
        payload = self._create_payload(username='doctor_one')
        response = self.client.post(self.STAFF_URL, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_never_exposes_password(self):
        self.auth(self.admin)
        response = self.client.post(
            self.STAFF_URL, self._create_payload(), format='json'
        )
        self.assertNotIn('password', response.data)
        self.assertNotIn('confirm_password', response.data)

    def test_doctor_cannot_create_staff(self):
        self.auth(self.doctor)
        response = self.client.post(
            self.STAFF_URL, self._create_payload(), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_create_staff(self):
        self.clear_auth()
        response = self.client.post(
            self.STAFF_URL, self._create_payload(), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==========================================================================
# STAFF UPDATE
# ==========================================================================

class TestStaffUpdate(UserTestBase):

    def test_admin_can_update_staff_details(self):
        self.auth(self.admin)
        response = self.client.patch(
            self.staff_url(self.doctor.id),
            {'first_name': 'Updated'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Updated')

    def test_cannot_promote_to_admin(self):
        self.auth(self.admin)
        response = self.client.patch(
            self.staff_url(self.doctor.id),
            {'role': 'admin'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_update_to_duplicate_email(self):
        self.auth(self.admin)
        response = self.client.patch(
            self.staff_url(self.doctor.id),
            {'email': 'receptionist@hmis.test'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_nonexistent_returns_404(self):
        self.auth(self.admin)
        response = self.client.patch(
            self.staff_url(99999),
            {'first_name': 'Ghost'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_doctor_cannot_update_another_staff(self):
        self.auth(self.doctor)
        response = self.client.patch(
            self.staff_url(self.receptionist.id),
            {'first_name': 'Hacked'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ==========================================================================
# STAFF DEACTIVATE
# ==========================================================================

class TestStaffDeactivate(UserTestBase):

    def test_admin_can_deactivate_staff(self):
        self.auth(self.admin)
        response = self.client.delete(self.staff_url(self.doctor.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.doctor.refresh_from_db()
        self.assertIsNotNone(self.doctor.deleted_at)
        self.assertFalse(self.doctor.is_active)

    def test_deactivated_staff_no_longer_in_list(self):
        self.auth(self.admin)
        self.client.delete(self.staff_url(self.doctor.id))

        response = self.client.get(self.STAFF_URL)
        usernames = [u['username'] for u in response.data]
        self.assertNotIn('doctor_one', usernames)

    def test_deactivate_nonexistent_returns_404(self):
        self.auth(self.admin)
        response = self.client.delete(self.staff_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_doctor_cannot_deactivate_staff(self):
        self.auth(self.doctor)
        response = self.client.delete(self.staff_url(self.receptionist.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_deactivate(self):
        self.clear_auth()
        response = self.client.delete(self.staff_url(self.doctor.id))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)