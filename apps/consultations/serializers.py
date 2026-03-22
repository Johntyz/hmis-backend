from rest_framework import serializers
from .models import Consultation
from apps.appointments.models import Appointment


class ConsultationWriteSerializer(serializers.ModelSerializer):
    """
    Used by the assigned doctor to create or update a consultation.
    - appointment and doctor are set automatically by the service layer
    - status changes are handled via a dedicated endpoint
    - created_by and updated_by are set automatically by the service layer
    """

    class Meta:
        model = Consultation
        fields = [
            'appointment',
            'diagnosis',
            'notes',
        ]

    def validate_appointment(self, value):
        # Appointment must not be soft deleted
        if value.deleted_at is not None:
            raise serializers.ValidationError(
                "Cannot create a consultation for a deleted appointment."
            )

        # Appointment must be in a valid state for consultation
        if value.status not in ['in_progress', 'completed']:
            raise serializers.ValidationError(
                f"Cannot create a consultation for an appointment "
                f"with status '{value.status}'. "
                f"Appointment must be in_progress or completed."
            )

        # Appointment must not already have a consultation
        # Exclude current instance on update
        instance = self.instance
        if instance is None:
            # Creating — check for existing consultation
            if Consultation.objects.filter(
                appointment=value,
                deleted_at__isnull=True
            ).exists():
                raise serializers.ValidationError(
                    "This appointment already has a consultation record."
                )

        return value


class ConsultationStatusSerializer(serializers.ModelSerializer):
    """
    Used to finalize a consultation.
    Transition rules are enforced at the service level.
    """

    class Meta:
        model = Consultation
        fields = ['status']


class ConsultationDoctorReadSerializer(serializers.ModelSerializer):
    """
    Full read serializer for doctors.
    Doctors see all clinical details of their own consultations.
    """
    patient_name = serializers.SerializerMethodField()
    appointment_date = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    prescriptions = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = [
            'id',
            'appointment',
            'appointment_date',
            'patient_name',
            'doctor_name',
            'diagnosis',
            'notes',
            'status',
            'status_display',
            'prescriptions',
            'created_at',
            'updated_at',
        ]

    def get_patient_name(self, obj):
        p = obj.appointment.patient
        return f"{p.first_name} {p.last_name}"

    def get_appointment_date(self, obj):
        return obj.appointment.appointment_date

    def get_doctor_name(self, obj):
        return f"Dr. {obj.doctor.get_full_name()}"

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_prescriptions(self, obj):
        # Inline active prescriptions for convenience
        return obj.prescriptions.filter(
            deleted_at__isnull=True
        ).values(
            'id', 'medication_name', 'dosage',
            'frequency', 'duration', 'instructions'
        )


class ConsultationAdminReadSerializer(serializers.ModelSerializer):
    """
    Admin read serializer.
    Admins see everything including audit trail fields.
    """
    patient_name = serializers.SerializerMethodField()
    appointment_date = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = [
            'id',
            'appointment',
            'appointment_date',
            'patient_name',
            'doctor_name',
            'diagnosis',
            'notes',
            'status',
            'status_display',
            'created_by_name',
            'updated_by_name',
            'created_at',
            'updated_at',
        ]

    def get_patient_name(self, obj):
        p = obj.appointment.patient
        return f"{p.first_name} {p.last_name}"

    def get_appointment_date(self, obj):
        return obj.appointment.appointment_date

    def get_doctor_name(self, obj):
        return f"Dr. {obj.doctor.get_full_name()}"

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None

    def get_updated_by_name(self, obj):
        return obj.updated_by.get_full_name() if obj.updated_by else None

    def get_status_display(self, obj):
        return obj.get_status_display()


class ConsultationReceptionistReadSerializer(serializers.ModelSerializer):
    """
    Restricted read serializer for receptionists.
    Receptionists can see appointment and patient info
    but NEVER clinical data — diagnosis, notes, prescriptions.
    This enforces patient data privacy at the API level.
    """
    patient_name = serializers.SerializerMethodField()
    appointment_date = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = [
            'id',
            'appointment',
            'appointment_date',
            'patient_name',
            'doctor_name',
            'status',
            'status_display',
            'created_at',
        ]

    def get_patient_name(self, obj):
        p = obj.appointment.patient
        return f"{p.first_name} {p.last_name}"

    def get_appointment_date(self, obj):
        return obj.appointment.appointment_date

    def get_doctor_name(self, obj):
        return f"Dr. {obj.doctor.get_full_name()}"

    def get_status_display(self, obj):
        return obj.get_status_display()