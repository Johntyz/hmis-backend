from rest_framework import serializers
from datetime import date
from .models import Patient


class PatientWriteSerializer(serializers.ModelSerializer):
    """
    Used for creating and updating patients.
    Enforces all input validation rules.
    """

    class Meta:
        model = Patient
        fields = [
            'first_name',
            'last_name',
            'date_of_birth',
            'gender',
            'national_id',
            'phone_number',
            'email',
            'address',
        ]

    def validate_date_of_birth(self, value):
        today = date.today()

        if value > today:
            raise serializers.ValidationError("Date of birth cannot be in the future.")

        # Reject unrealistically old dates (older than 150 years)
        if (today.year - value.year) > 150:
            raise serializers.ValidationError("Date of birth is not realistic.")

        return value

    def validate_phone_number(self, value):
        # Strip spaces and dashes for normalization
        cleaned = value.replace(' ', '').replace('-', '')

        if not cleaned.isdigit():
            raise serializers.ValidationError("Phone number must contain only digits.")

        # Accept Kenyan formats: 07XXXXXXXX (10 digits) or 2547XXXXXXXX (12 digits)
        if len(cleaned) not in [10, 12]:
            raise serializers.ValidationError(
                "Phone number must be 10 digits (07XXXXXXXX) "
                "or 12 digits with country code (2547XXXXXXXX)."
            )

        return cleaned

    def validate_email(self, value):
        if value:
            # Normalize to lowercase to avoid duplicate emails
            return value.lower()
        return value

    def validate_national_id(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("National ID must contain only digits.")
        if len(value) not in [7, 8]:
            raise serializers.ValidationError("National ID must be 7 or 8 digits.")
        return value

    def validate(self, data):
        """
        Cross-field validation.
        Check uniqueness manually here so we can provide
        clear, user-friendly error messages.
        On update, exclude the current instance from uniqueness checks.
        """
        instance = self.instance  # None on create, Patient instance on update

        phone = data.get('phone_number')
        email = data.get('email')
        national_id = data.get('national_id')

        phone_qs = Patient.objects.filter(phone_number=phone, deleted_at__isnull=True)
        id_qs = Patient.objects.filter(national_id=national_id, deleted_at__isnull=True)

        if instance:
            phone_qs = phone_qs.exclude(id=instance.id)
            id_qs = id_qs.exclude(id=instance.id)

        if phone_qs.exists():
            raise serializers.ValidationError(
                {"phone_number": "A patient with this phone number already exists."}
            )

        if id_qs.exists():
            raise serializers.ValidationError(
                {"national_id": "A patient with this National ID already exists."}
            )

        if email:
            email_qs = Patient.objects.filter(email=email, deleted_at__isnull=True)
            if instance:
                email_qs = email_qs.exclude(id=instance.id)
            if email_qs.exists():
                raise serializers.ValidationError(
                    {"email": "A patient with this email already exists."}
                )

        return data


class PatientReadSerializer(serializers.ModelSerializer):
    """
    Safe read-only representation of a patient.
    Includes computed fields for convenience.
    """
    full_name = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',
            'first_name',
            'last_name',
            'date_of_birth',
            'age',
            'gender',
            'national_id',
            'phone_number',
            'email',
            'address',
            'created_at',
            'updated_at',
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_age(self, obj):
        today = date.today()
        dob = obj.date_of_birth
        return today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )