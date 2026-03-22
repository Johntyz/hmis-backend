from django.utils import timezone
from datetime import timedelta
from .models import Appointment


class AppointmentService:
    """
    Service layer for appointment business logic.
    Responsibilities:
    - Creating appointments
    - Updating appointments
    - Status transition enforcement
    - Doctor notes updates
    - Overlap and buffer checking
    - Fetching appointments (role-scoped)
    - Soft deleting appointments
    All business rules are enforced here before any database write.
    """

    # Minimum buffer between appointments in minutes
    BUFFER_MINUTES = 15

    @staticmethod
    def _check_doctor_availability(doctor, appointment_date, duration_minutes, exclude_id=None):
        """
        Checks whether a doctor has a conflicting appointment.
        Accounts for appointment duration and buffer time.

        An appointment conflicts if it overlaps with the
        requested slot including the buffer window.
        """
        buffer = timedelta(minutes=AppointmentService.BUFFER_MINUTES)
        new_start = appointment_date
        new_end = appointment_date + timedelta(minutes=duration_minutes) + buffer

        existing = Appointment.objects.filter(
            doctor=doctor,
            deleted_at__isnull=True,
            status__in=['scheduled', 'confirmed', 'in_progress']
        )

        if exclude_id:
            existing = existing.exclude(id=exclude_id)

        for appt in existing:
            existing_start = appt.appointment_date
            existing_end = appt.appointment_date + timedelta(minutes=appt.duration_minutes) + buffer

            # Check for overlap
            if new_start < existing_end and new_end > existing_start:
                return False

        return True

    @staticmethod
    def _check_patient_availability(patient, appointment_date, duration_minutes, exclude_id=None):
        """
        Checks whether a patient already has an appointment
        at the requested time slot.
        """
        buffer = timedelta(minutes=AppointmentService.BUFFER_MINUTES)
        new_start = appointment_date
        new_end = appointment_date + timedelta(minutes=duration_minutes) + buffer

        existing = Appointment.objects.filter(
            patient=patient,
            deleted_at__isnull=True,
            status__in=['scheduled', 'confirmed', 'in_progress']
        )

        if exclude_id:
            existing = existing.exclude(id=exclude_id)

        for appt in existing:
            existing_start = appt.appointment_date
            existing_end = appt.appointment_date + timedelta(minutes=appt.duration_minutes) + buffer

            if new_start < existing_end and new_end > existing_start:
                return False

        return True

    @staticmethod
    def create_appointment(validated_data):
        """
        Creates a new appointment.
        Business rules enforced:
        - Appointment date cannot be in the past
        - Doctor must not have a conflicting appointment (including buffer)
        - Patient must not have a conflicting appointment
        """
        doctor = validated_data.get('doctor')
        patient = validated_data.get('patient')
        appointment_date = validated_data.get('appointment_date')
        duration_minutes = validated_data.get('duration_minutes', 30)

        if appointment_date < timezone.now():
            raise ValueError("Appointment date cannot be in the past.")

        if not AppointmentService._check_doctor_availability(doctor, appointment_date, duration_minutes):
            raise ValueError(
                "Doctor already has an appointment during this time slot. "
                "Please allow at least 15 minutes between appointments."
            )

        if not AppointmentService._check_patient_availability(patient, appointment_date, duration_minutes):
            raise ValueError("Patient already has an appointment during this time slot.")

        return Appointment.objects.create(**validated_data)

    @staticmethod
    def update_appointment(appointment_id, validated_data):
        """
        Updates an existing appointment.
        Business rules enforced:
        - Cannot update a completed or cancelled appointment
        - Doctor conflict check excludes current appointment
        - Patient conflict check excludes current appointment
        """
        appointment = Appointment.objects.filter(
            id=appointment_id,
            deleted_at__isnull=True
        ).first()

        if not appointment:
            raise ValueError("Appointment not found.")

        if appointment.status in ['completed', 'cancelled', 'no_show']:
            raise ValueError(
                f"Cannot update an appointment with status '{appointment.status}'."
            )

        doctor = validated_data.get('doctor', appointment.doctor)
        patient = validated_data.get('patient', appointment.patient)
        appointment_date = validated_data.get('appointment_date', appointment.appointment_date)
        duration_minutes = validated_data.get('duration_minutes', appointment.duration_minutes)

        if not AppointmentService._check_doctor_availability(
            doctor, appointment_date, duration_minutes, exclude_id=appointment_id
        ):
            raise ValueError(
                "Doctor already has an appointment during this time slot. "
                "Please allow at least 15 minutes between appointments."
            )

        if not AppointmentService._check_patient_availability(
            patient, appointment_date, duration_minutes, exclude_id=appointment_id
        ):
            raise ValueError("Patient already has an appointment during this time slot.")

        for field, value in validated_data.items():
            setattr(appointment, field, value)

        appointment.save()
        return appointment

    @staticmethod
    def update_status(appointment_id, new_status, requesting_user):
        """
        Updates appointment status with strict transition rules.
        Business rules enforced:
        - Only valid transitions are allowed
        - Only the assigned doctor can mark in_progress, completed, no_show
        - Receptionists and admins can confirm or cancel
        """
        appointment = Appointment.objects.filter(
            id=appointment_id,
            deleted_at__isnull=True
        ).first()

        if not appointment:
            raise ValueError("Appointment not found.")

        current_status = appointment.status
        valid_next = Appointment.VALID_TRANSITIONS.get(current_status, [])

        if new_status not in valid_next:
            raise ValueError(
                f"Cannot transition from '{current_status}' to '{new_status}'. "
                f"Valid transitions: {valid_next}."
            )

        # Doctor-only transitions
        doctor_only_statuses = ['in_progress', 'completed', 'no_show']
        if new_status in doctor_only_statuses:
            if requesting_user.role != 'doctor' or appointment.doctor != requesting_user:
                raise ValueError(
                    f"Only the assigned doctor can mark an appointment as '{new_status}'."
                )

        appointment.status = new_status
        appointment.save()
        return appointment

    @staticmethod
    def update_notes(appointment_id, notes, requesting_user):
        """
        Allows the assigned doctor to write consultation notes.
        Business rules enforced:
        - Only the assigned doctor can write notes
        - Cannot add notes to a cancelled or no_show appointment
        """
        appointment = Appointment.objects.filter(
            id=appointment_id,
            deleted_at__isnull=True
        ).first()

        if not appointment:
            raise ValueError("Appointment not found.")

        if appointment.doctor != requesting_user:
            raise ValueError("Only the assigned doctor can write notes for this appointment.")

        if appointment.status in ['cancelled', 'no_show']:
            raise ValueError("Cannot add notes to a cancelled or no-show appointment.")

        appointment.notes = notes
        appointment.save()
        return appointment

    @staticmethod
    def list_appointments(requesting_user):
        """
        Returns appointments scoped to the requesting user's role.
        - Doctors see only their own appointments
        - Admins and receptionists see all appointments
        """
        queryset = Appointment.objects.filter(deleted_at__isnull=True).select_related(
            'patient', 'doctor'
        ).order_by('appointment_date')

        if requesting_user.role == 'doctor':
            return queryset.filter(doctor=requesting_user)

        return queryset

    @staticmethod
    def get_appointment_by_id(appointment_id):
        """
        Retrieves a single active appointment.
        Returns None if not found or soft deleted.
        """
        return Appointment.objects.filter(
            id=appointment_id,
            deleted_at__isnull=True
        ).select_related('patient', 'doctor').first()

    @staticmethod
    def soft_delete_appointment(appointment_id, requesting_user):
        """
        Soft deletes an appointment.
        Business rules enforced:
        - Cannot delete a completed appointment
        - Doctors can only cancel their own appointments
        - Admins and receptionists can cancel any appointment
        Raises ValueError so the view can respond with appropriate HTTP status.
        """
        appointment = Appointment.objects.filter(
            id=appointment_id,
            deleted_at__isnull=True
        ).first()

        if not appointment:
            raise ValueError("Appointment not found.")

        if appointment.status == 'completed':
            raise ValueError("Cannot delete a completed appointment.")

        if requesting_user.role == 'doctor' and appointment.doctor != requesting_user:
            raise ValueError("You can only cancel your own appointments.")

        appointment.deleted_at = timezone.now()
        appointment.status = 'cancelled'
        appointment.save()
        return appointment