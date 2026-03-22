from rest_framework import serializers
from django.utils import timezone
from .models import Appointment
from apps.users.models import CustomUser
from apps.patients.models import Patient


class AppointmentWriteSerializer(serializers.ModelSerializer):
    """
    Used by receptionists and admins to create and update appointments.
    Doctors cannot create appointments — they are assigned to them.
    Notes are excluded here — doctors write notes via a separate serializer.
    """

    class Meta:
        model = Appointment
        fields = [
            'patient',
            'doctor',
            'appointment_date',
            'duration_minutes',
            'reason',
        ]

    def validate_doctor(self, value):
    # Must be a doctor role
        if value.role != 'doctor':
            raise serializers.ValidationError("Selected user is not a doctor.")

        # Must be an active doctor
        if not value.is_active:
            raise serializers.ValidationError("Selected doctor is not active.")

        return value
    def validate_patient(self, value):
        # Patient must not be soft deleted
        if value.deleted_at is not None:
            raise serializers.ValidationError("Selected patient record has been deactivated.")
        return value

    def validate_appointment_date(self, value):
        # Cannot schedule in the past
        if value < timezone.now():
            raise serializers.ValidationError("Appointment date cannot be in the past.")

        # Cannot schedule more than 1 year in advance
        from datetime import timedelta
        if value > timezone.now() + timedelta(days=365):
            raise serializers.ValidationError("Appointment cannot be scheduled more than 1 year in advance.")

        return value

    def validate_duration_minutes(self, value):
        if value < 10:
            raise serializers.ValidationError("Appointment duration must be at least 10 minutes.")
        if value > 480:
            raise serializers.ValidationError("Appointment duration cannot exceed 8 hours.")
        return value


class AppointmentNotesSerializer(serializers.ModelSerializer):
    """
    Used exclusively by the assigned doctor to write consultation notes.
    Only the notes field is writable here.
    """

    class Meta:
        model = Appointment
        fields = ['notes']


class AppointmentStatusSerializer(serializers.ModelSerializer):
    """
    Used to update appointment status.
    Transition rules are enforced at the service level.
    """

    class Meta:
        model = Appointment
        fields = ['status']


class AppointmentReadSerializer(serializers.ModelSerializer):
    """
    Safe read-only representation of an appointment.
    Includes expanded patient and doctor info.
    """
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient',
            'patient_name',
            'doctor',
            'doctor_name',
            'appointment_date',
            'duration_minutes',
            'status',
            'status_display',
            'reason',
            'notes',
            'created_at',
            'updated_at',
        ]

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"

    def get_doctor_name(self, obj):
        return f"Dr. {obj.doctor.get_full_name()}"

    def get_status_display(self, obj):
        return obj.get_status_display()