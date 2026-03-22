"""
Service layer tests for UserService.

Tests call service methods directly — no HTTP involved.
Verifies all business rules raise the correct ValueError.

Test groups:
    TestCreateStaff         → creation rules
    TestUpdateStaff         → update rules
    TestDeactivateStaff     → soft delete / deactivation rules
    TestListAndGetStaff     → query methods
    TestChangePassword      → password change rules
"""

from django.utils import timezone
from apps.users.services import UserService
from apps.users.models import CustomUser
from .base import UserTestBase


# ==========================================================================
# CREATE
# ==========================================================================

class TestCreateStaff(UserTestBase):

    def test_can_create_doctor(self):
        user = UserService.create_staff({
            'username': 'new_doctor',
            'password': self.PASSWORD,
            'role': 'doctor',
            'email': 'newdoctor@hmis.test',
            'first_name': 'New',
            'last_name': 'Doctor',
        })
        self.assertEqual(user.role, 'doctor')
        self.assertIsNotNone(user.pk)

    def test_can_create_receptionist(self):
        user = UserService.create_staff({
            'username': 'new_receptionist',
            'password': self.PASSWORD,
            'role': 'receptionist',
            'email': 'newreceptionist@hmis.test',
        })
        self.assertEqual(user.role, 'receptionist')

    def test_cannot_create_admin_via_api(self):
        with self.assertRaises(ValueError) as ctx:
            UserService.create_staff({
                'username': 'rogue_admin',
                'password': self.PASSWORD,
                'role': 'admin',
                'email': 'rogueadmin@hmis.test',
            })
        self.assertIn('Admin', str(ctx.exception))

    def test_duplicate_email_raises_error(self):
        """Email uniqueness is enforced at the service level."""
        with self.assertRaises(ValueError) as ctx:
            UserService.create_staff({
                'username': 'another_doctor',
                'password': self.PASSWORD,
                'role': 'doctor',
                'email': 'doctor@hmis.test',  # already used by self.doctor
            })
        self.assertIn('email', str(ctx.exception).lower())


# ==========================================================================
# UPDATE
# ==========================================================================

class TestUpdateStaff(UserTestBase):

    def test_can_update_staff_name(self):
        updated = UserService.update_staff(
            self.doctor.id,
            {'first_name': 'Updated', 'last_name': 'Name'}
        )
        self.assertEqual(updated.first_name, 'Updated')

    def test_cannot_assign_admin_role(self):
        with self.assertRaises(ValueError) as ctx:
            UserService.update_staff(self.doctor.id, {'role': 'admin'})
        self.assertIn('admin', str(ctx.exception).lower())

    def test_cannot_update_soft_deleted_user(self):
        self.doctor.deleted_at = timezone.now()
        self.doctor.save()

        with self.assertRaises(ValueError) as ctx:
            UserService.update_staff(self.doctor.id, {'first_name': 'Ghost'})
        self.assertIn('not found', str(ctx.exception).lower())

    def test_cannot_update_nonexistent_user(self):
        with self.assertRaises(ValueError) as ctx:
            UserService.update_staff(99999, {'first_name': 'Nobody'})
        self.assertIn('not found', str(ctx.exception).lower())

    def test_email_update_blocks_duplicate(self):
        """Cannot update email to one already used by another user."""
        with self.assertRaises(ValueError) as ctx:
            UserService.update_staff(
                self.doctor.id,
                {'email': 'receptionist@hmis.test'}  # used by self.receptionist
            )
        self.assertIn('email', str(ctx.exception).lower())

    def test_email_update_allows_same_email(self):
        """A user can 'update' their email to their current email without error."""
        updated = UserService.update_staff(
            self.doctor.id,
            {'email': 'doctor@hmis.test'}  # same as current
        )
        self.assertEqual(updated.email, 'doctor@hmis.test')


# ==========================================================================
# DEACTIVATE
# ==========================================================================

class TestDeactivateStaff(UserTestBase):

    def test_can_deactivate_active_staff(self):
        UserService.deactivate_staff(self.doctor.id)
        self.doctor.refresh_from_db()
        self.assertIsNotNone(self.doctor.deleted_at)
        self.assertFalse(self.doctor.is_active)

    def test_deactivated_user_cannot_log_in(self):
        """is_active=False blocks Django's authenticate()."""
        UserService.deactivate_staff(self.doctor.id)
        from django.contrib.auth import authenticate
        user = authenticate(username='doctor_one', password=self.PASSWORD)
        self.assertIsNone(user)

    def test_cannot_deactivate_already_deleted_user(self):
        self.doctor.deleted_at = timezone.now()
        self.doctor.save()

        with self.assertRaises(ValueError) as ctx:
            UserService.deactivate_staff(self.doctor.id)
        self.assertIn('not found', str(ctx.exception).lower())

    def test_cannot_deactivate_nonexistent_user(self):
        with self.assertRaises(ValueError) as ctx:
            UserService.deactivate_staff(99999)
        self.assertIn('not found', str(ctx.exception).lower())


# ==========================================================================
# LIST & GET
# ==========================================================================

class TestListAndGetStaff(UserTestBase):

    def test_list_returns_active_non_superusers(self):
        staff = UserService.list_staff()
        usernames = list(staff.values_list('username', flat=True))
        self.assertIn('doctor_one', usernames)
        self.assertIn('receptionist_one', usernames)
        self.assertNotIn('admin_one', usernames)  # superuser excluded

    def test_list_excludes_soft_deleted(self):
        self.doctor.deleted_at = timezone.now()
        self.doctor.save()

        staff = UserService.list_staff()
        usernames = list(staff.values_list('username', flat=True))
        self.assertNotIn('doctor_one', usernames)

    def test_get_staff_by_id_returns_correct_user(self):
        user = UserService.get_staff_by_id(self.doctor.id)
        self.assertEqual(user.id, self.doctor.id)

    def test_get_staff_returns_none_for_soft_deleted(self):
        self.doctor.deleted_at = timezone.now()
        self.doctor.save()
        user = UserService.get_staff_by_id(self.doctor.id)
        self.assertIsNone(user)

    def test_get_staff_returns_none_for_superuser(self):
        """Superusers are excluded from regular staff queries."""
        user = UserService.get_staff_by_id(self.admin.id)
        self.assertIsNone(user)

    def test_get_staff_returns_none_for_nonexistent(self):
        user = UserService.get_staff_by_id(99999)
        self.assertIsNone(user)


# ==========================================================================
# CHANGE PASSWORD
# ==========================================================================

class TestChangePassword(UserTestBase):

    def test_correct_old_password_allows_change(self):
        UserService.change_password(self.doctor, self.PASSWORD, self.NEW_PASSWORD)
        self.doctor.refresh_from_db()
        self.assertTrue(self.doctor.check_password(self.NEW_PASSWORD))

    def test_wrong_old_password_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            UserService.change_password(self.doctor, 'WrongPassword!', self.NEW_PASSWORD)
        self.assertIn('incorrect', str(ctx.exception).lower())

    def test_same_password_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            UserService.change_password(self.doctor, self.PASSWORD, self.PASSWORD)
        self.assertIn('different', str(ctx.exception).lower())

    def test_password_is_actually_updated_in_db(self):
        """After change, the old password must no longer work."""
        UserService.change_password(self.doctor, self.PASSWORD, self.NEW_PASSWORD)
        self.doctor.refresh_from_db()
        self.assertFalse(self.doctor.check_password(self.PASSWORD))
        self.assertTrue(self.doctor.check_password(self.NEW_PASSWORD))


class TestReactivateStaff(UserTestBase):
 
    def test_can_reactivate_soft_deleted_staff(self):
        UserService.deactivate_staff(self.doctor.id)
        UserService.reactivate_staff(self.doctor.id)
 
        self.doctor.refresh_from_db()
        self.assertIsNone(self.doctor.deleted_at)
        self.assertTrue(self.doctor.is_active)
 
    def test_reactivated_user_can_log_in(self):
        UserService.deactivate_staff(self.doctor.id)
        UserService.reactivate_staff(self.doctor.id)
 
        from django.contrib.auth import authenticate
        user = authenticate(username='doctor_one', password=self.PASSWORD)
        self.assertIsNotNone(user)
 
    def test_cannot_reactivate_already_active_staff(self):
        with self.assertRaises(ValueError) as ctx:
            UserService.reactivate_staff(self.doctor.id)
        self.assertIn('already active', str(ctx.exception).lower())
 
    def test_cannot_reactivate_nonexistent_staff(self):
        with self.assertRaises(ValueError) as ctx:
            UserService.reactivate_staff(99999)
        self.assertIn('not found', str(ctx.exception).lower())
 
 
class TestResetPassword(UserTestBase):
 
    def test_admin_can_reset_staff_password(self):
        UserService.reset_password(self.doctor.id, self.NEW_PASSWORD)
        self.doctor.refresh_from_db()
        self.assertTrue(self.doctor.check_password(self.NEW_PASSWORD))
 
    def test_old_password_no_longer_works_after_reset(self):
        UserService.reset_password(self.doctor.id, self.NEW_PASSWORD)
        self.doctor.refresh_from_db()
        self.assertFalse(self.doctor.check_password(self.PASSWORD))
 
    def test_reset_nonexistent_staff_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            UserService.reset_password(99999, self.NEW_PASSWORD)
        self.assertIn('not found', str(ctx.exception).lower())
 
    def test_reset_soft_deleted_staff_raises_error(self):
        self.doctor.deleted_at = timezone.now()
        self.doctor.save()
 
        with self.assertRaises(ValueError) as ctx:
            UserService.reset_password(self.doctor.id, self.NEW_PASSWORD)
        self.assertIn('not found', str(ctx.exception).lower())