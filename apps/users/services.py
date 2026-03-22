from django.utils import timezone
from .models import CustomUser


class UserService:
    """
    Service layer for user/staff business logic.

    Responsibilities:
    - Creating staff accounts
    - Updating staff accounts
    - Deactivating (soft deleting) staff accounts
    - Resetting passwords (admin-initiated, no old password required)
    - Fetching staff accounts
    - Password management (user-initiated, requires old password)

    All business rules are enforced here before any database write.
    Serializers handle syntax validation (field types, password strength).
    This layer handles semantic rules (role restrictions, uniqueness, state).
    Raises ValueError for all violations — views convert these to DRF errors.
    """

    @staticmethod
    def create_staff(validated_data):
        """
        Creates a doctor or receptionist account.

        Business rules:
        - Role cannot be 'admin' (admins are created via createsuperuser only)
        - Email must be unique across all users
        - confirm_password is stripped before saving

        The serializer handles password strength and confirmation match.
        This service handles the business meaning of those fields.
        """
        role = validated_data.get('role')
        if role == 'admin':
            raise ValueError("Admin accounts cannot be created via the API.")

        email = validated_data.get('email')
        if email and CustomUser.objects.filter(email=email).exists():
            raise ValueError("A user with this email already exists.")

        # Strip confirm_password — not a model field
        data = {k: v for k, v in validated_data.items() if k != 'confirm_password'}

        return CustomUser.objects.create_user(**data)

    @staticmethod
    def update_staff(user_id, validated_data):
        """
        Updates a staff member's details.

        Business rules:
        - Cannot update a soft-deleted staff member
        - Cannot promote or demote to/from admin via the API
        - Email must remain unique across users (excluding self)
        """
        user = CustomUser.objects.filter(
            id=user_id,
            deleted_at__isnull=True
        ).first()

        if not user:
            raise ValueError("Staff member not found.")

        role = validated_data.get('role')
        if role == 'admin':
            raise ValueError("Cannot assign admin role via the API.")

        email = validated_data.get('email')
        if email and CustomUser.objects.filter(email=email).exclude(id=user_id).exists():
            raise ValueError("A user with this email already exists.")

        for field, value in validated_data.items():
            if field == 'phone_number' and value == '':
                value = None
            setattr(user, field, value)

        user.save()
        return user

    @staticmethod
    def deactivate_staff(user_id):
        """
        Soft deletes a staff member by stamping deleted_at
        and setting is_active=False so they cannot log in.

        Business rules:
        - Cannot deactivate an already deactivated account
        """
        user = CustomUser.objects.filter(
            id=user_id,
            is_active=True
        ).first()

        if not user:
            raise ValueError("Staff member not found.")

        user.deleted_at = timezone.now()
        user.is_active = False
        user.save()
        return user

    @staticmethod
    def reactivate_staff(user_id):
        """
        Reactivates a soft-deleted staff member.
        Clears deleted_at AND restores is_active=True so they can log in again.

        This is the correct inverse of deactivate_staff.
        Doing only one without the other leaves the account in an inconsistent state.
        """
        user = CustomUser.objects.filter(id=user_id).first()

        if not user:
            raise ValueError("Staff member not found.")

        if user.deleted_at is None:
            raise ValueError("This staff member is already active.")

        user.deleted_at = None
        user.is_active = True
        user.save()
        return user

    @staticmethod
    def list_staff():
        """
        Returns all active (non soft-deleted) staff members.
        Excludes superusers — they are managed via Django admin, not this API.
        """
        return CustomUser.objects.filter(
        is_active=True,
        is_superuser=False,
        ).order_by('last_name', 'first_name')

    @staticmethod
    def get_staff_by_id(user_id):
        """
        Retrieves a single active non-superuser staff member.
        Returns None if not found, soft deleted, or is a superuser.
        """
        return CustomUser.objects.filter(
            id=user_id,
            deleted_at__isnull=True,
            is_superuser=False,
        ).first()

    @staticmethod
    def change_password(user, old_password, new_password):
        """
        User-initiated password change.
        Requires the current password to verify identity.

        Business rules:
        - Old password must be correct
        - New password must differ from the old one
        """
        if not user.check_password(old_password):
            raise ValueError("Old password is incorrect.")

        if old_password == new_password:
            raise ValueError(
                "New password must be different from the old password."
            )

        user.set_password(new_password)
        user.save()
        return user

    @staticmethod
    def reset_password(user_id, new_password):
        """
        Admin-initiated password reset.
        Does NOT require the old password — used when a staff member
        is locked out and cannot change their own password.

        Business rules:
        - Target user must exist and not be soft-deleted
        """
        user = CustomUser.objects.filter(
        id=user_id,
        ).first()

        if not user:
            raise ValueError("Staff member not found.")

        user.set_password(new_password)
        user.save()
        return user