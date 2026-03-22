from rest_framework import serializers
from .models import Prescription


class PrescriptionWriteSerializer(serializers.ModelSerializer):
    """
    Used by the assigned doctor to create or update a prescription.
    - consultation is provided by the client
    - patient, created_by, updated_by are set automatically by the service
    - status changes are handled via a dedicated endpoint
    - consultation is locked after creation (read_only on update)
    """

    class Meta:
        model = Prescription
        fields = [
            'consultation',
            'medication_name',
            'dosage',
            'frequency',
            'duration',
            'instructions',
        ]

    def validate_consultation(self, value):
        # Consultation must not be soft deleted
        if value.deleted_at is not None:
            raise serializers.ValidationError(
                "Cannot prescribe for a deleted consultation."
            )

        # Consultation must not be finalized
        # Doctors add prescriptions while consultation is in draft
        if value.status == 'finalized':
            raise serializers.ValidationError(
                "Cannot add prescriptions to a finalized consultation. "
                "Finalized records are locked."
            )

        return value

    def validate_medication_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Medication name cannot be blank.")
        return value.strip()

    def validate_dosage(self, value):
        if not value.strip():
            raise serializers.ValidationError("Dosage cannot be blank.")
        return value.strip()

    def validate_frequency(self, value):
        if not value.strip():
            raise serializers.ValidationError("Frequency cannot be blank.")
        return value.strip()

    def validate_duration(self, value):
        if not value.strip():
            raise serializers.ValidationError("Duration cannot be blank.")
        return value.strip()


class PrescriptionStatusSerializer(serializers.ModelSerializer):
    """
    Used to update prescription status.
    Transition rules are enforced at the service level.
    """

    class Meta:
        model = Prescription
        fields = ['status']


class PrescriptionDoctorReadSerializer(serializers.ModelSerializer):
    """
    Full read serializer for doctors.
    Doctors see all prescription details for their own patients.
    """
    patient_name = serializers.SerializerMethodField()
    consultation_id = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = [
            'id',
            'consultation_id',
            'patient_name',
            'medication_name',
            'dosage',
            'frequency',
            'duration',
            'instructions',
            'status',
            'status_display',
            'created_by_name',
            'created_at',
            'updated_at',
        ]

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"

    def get_consultation_id(self, obj):
        return obj.consultation.id

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None


class PrescriptionAdminReadSerializer(serializers.ModelSerializer):
    """
    Admin read serializer.
    Admins see everything including full audit trail.
    """
    patient_name = serializers.SerializerMethodField()
    consultation_id = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = [
            'id',
            'consultation_id',
            'patient_name',
            'medication_name',
            'dosage',
            'frequency',
            'duration',
            'instructions',
            'status',
            'status_display',
            'created_by_name',
            'updated_by_name',
            'created_at',
            'updated_at',
        ]

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"

    def get_consultation_id(self, obj):
        return obj.consultation.id

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None

    def get_updated_by_name(self, obj):
        return obj.updated_by.get_full_name() if obj.updated_by else None


class PrescriptionReceptionistReadSerializer(serializers.ModelSerializer):
    """
    Restricted read serializer for receptionists.
    Receptionists can see medication name and patient
    for administrative purposes (e.g. billing, dispensing coordination)
    but cannot see clinical dosage details or instructions.

    This enforces patient data privacy at the API level.
    """
    patient_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = [
            'id',
            'patient_name',
            'medication_name',
            'status',
            'status_display',
            'created_at',
        ]

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"

    def get_status_display(self, obj):
        return obj.get_status_display()