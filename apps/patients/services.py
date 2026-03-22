from django.utils import timezone
from .models import Patient
# Import needed for search_patients Q filter
from django.db import models

class PatientService:
    """
    Service layer for Patient business logic.
    Responsibilities:
    - Creating patient records
    - Updating patient records
    - Fetching patient records
    - Soft deleting patient records
    All business rules are enforced here before any database write.
    """

    @staticmethod
    def create_patient(validated_data):
        """
        Creates a new patient record.
        Business rules enforced:
        - No duplicate phone number among active patients
        - No duplicate national ID among active patients
        - No duplicate email among active patients
        Note: uniqueness is also checked at serializer level.
        The service is a second line of defense.
        """
        phone = validated_data.get('phone_number')
        national_id = validated_data.get('national_id')
        email = validated_data.get('email')

        if Patient.objects.filter(phone_number=phone, deleted_at__isnull=True).exists():
            raise ValueError("A patient with this phone number already exists.")

        if Patient.objects.filter(national_id=national_id, deleted_at__isnull=True).exists():
            raise ValueError("A patient with this National ID already exists.")

        if email and Patient.objects.filter(email=email, deleted_at__isnull=True).exists():
            raise ValueError("A patient with this email already exists.")

        return Patient.objects.create(**validated_data)

    @staticmethod
    def update_patient(patient_id, validated_data):
        """
        Updates an existing patient record.
        Business rules enforced:
        - Cannot update a soft-deleted patient
        - No duplicate phone number among other active patients
        - No duplicate national ID among other active patients
        - No duplicate email among other active patients
        """
        patient = Patient.objects.filter(
            id=patient_id,
            deleted_at__isnull=True
        ).first()

        if not patient:
            raise ValueError("Patient not found.")

        phone = validated_data.get('phone_number', patient.phone_number)
        national_id = validated_data.get('national_id', patient.national_id)
        email = validated_data.get('email', patient.email)

        if Patient.objects.filter(
            phone_number=phone,
            deleted_at__isnull=True
        ).exclude(id=patient_id).exists():
            raise ValueError("A patient with this phone number already exists.")

        if Patient.objects.filter(
            national_id=national_id,
            deleted_at__isnull=True
        ).exclude(id=patient_id).exists():
            raise ValueError("A patient with this National ID already exists.")

        if email and Patient.objects.filter(
            email=email,
            deleted_at__isnull=True
        ).exclude(id=patient_id).exists():
            raise ValueError("A patient with this email already exists.")

        for field, value in validated_data.items():
            setattr(patient, field, value)

        patient.save()
        return patient

    @staticmethod
    def list_patients():
        """
        Returns all active (non soft-deleted) patients.
        """
        return Patient.objects.filter(deleted_at__isnull=True).order_by('last_name', 'first_name')

    @staticmethod
    def get_patient_by_id(patient_id):
        """
        Retrieves a single active patient by ID.
        Returns None if not found or soft deleted.
        """
        return Patient.objects.filter(
            id=patient_id,
            deleted_at__isnull=True
        ).first()

    @staticmethod
    def search_patients(query):
        """
        Searches active patients by name, phone number, or national ID.
        Useful for receptionists looking up a patient quickly.
        """
        return Patient.objects.filter(
            deleted_at__isnull=True
        ).filter(
            models.Q(first_name__icontains=query) |
            models.Q(last_name__icontains=query) |
            models.Q(phone_number__icontains=query) |
            models.Q(national_id__icontains=query)
        ).order_by('last_name', 'first_name')

    @staticmethod
    def soft_delete_patient(patient_id):
        """
        Soft deletes a patient by setting deleted_at timestamp.
        Medical records are never permanently erased.
        Business rules enforced:
        - Cannot delete an already deleted patient
        Raises ValueError instead of returning None so the
        view can distinguish between not found and already deleted.
        """
        patient = Patient.objects.filter(
            id=patient_id,
            deleted_at__isnull=True
        ).first()

        if not patient:
            raise ValueError("Patient not found.")

        patient.deleted_at = timezone.now()
        patient.save()
        return patient
    

    @staticmethod
    def list_deleted_patients():
        """
        Returns all soft-deleted patients.
        Used by admin to review and reactivate deleted records.
        """
        return Patient.objects.filter(
            deleted_at__isnull=False
        ).order_by('-deleted_at')

    @staticmethod
    def reactivate_patient(patient_id):
        """
        Reactivates a soft-deleted patient by clearing deleted_at.
        """
        patient = Patient.objects.filter(
            id=patient_id,
            deleted_at__isnull=False
        ).first()

        if not patient:
            raise ValueError("Deleted patient not found.")

        patient.deleted_at = None
        patient.save()
        return patient


