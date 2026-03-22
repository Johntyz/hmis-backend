from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser


class StaffCreateSerializer(serializers.ModelSerializer):
    """
    Used by admins to create doctor or receptionist accounts.

    Validation responsibility:
        - Syntax/field-level validation lives here (password strength,
          confirmation match, role whitelist).
        - Business rule validation (duplicate email) lives in UserService.
          The serializer does NOT duplicate those checks.
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'first_name',
            'last_name', 'phone_number', 'role',
            'password', 'confirm_password',
        ]

    def validate_role(self, value):
        """Admin accounts are only created via createsuperuser."""
        if value == 'admin':
            raise serializers.ValidationError(
                "Admin accounts cannot be created via the API."
            )
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return data


class StaffUpdateSerializer(serializers.ModelSerializer):
    """
    Used by admins to update staff details, or by users updating their own profile.
    Password changes are handled via dedicated endpoints.
    """

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'first_name',
            'last_name', 'phone_number', 'role', 'is_active',
        ]

    def validate_role(self, value):
        if value == 'admin':
            raise serializers.ValidationError(
                "Cannot assign admin role via the API."
            )
        return value


class StaffReadSerializer(serializers.ModelSerializer):
    """
    Safe read-only representation of a staff member.
    Never exposes password or sensitive internals.
    """

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name',
            'last_name', 'phone_number', 'role', 'is_active',
            'date_joined',
        ]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    """
    For authenticated users changing their own password.
    Requires the current password to verify identity.
    """
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError(
                {"confirm_new_password": "Passwords do not match."}
            )
        return data


class AdminPasswordResetSerializer(serializers.Serializer):
    """
    For admins resetting a staff member's password.
    Does NOT require the old password — used for locked-out accounts.
    """
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError(
                {"confirm_new_password": "Passwords do not match."}
            )
        return data