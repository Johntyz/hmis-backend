from django.utils import timezone
from .models import Consultation


class ConsultationService:
    """
    Service layer for Consultation business logic.
    Responsibilities:
    - Creating consultations
    - Updating consultations
    - Finalizing consultations
    - Fetching consultations (role-scoped)
    - Soft deleting consultations
    All business rules are enforced here before any database write.
    Raises ValueError for business rule violations — never Django's
    PermissionDenied — so that views can respond with consistent
    DRF error formatting.
    """

    @staticmethod
    def create_consultation(validated_data, requesting_user):
        """
        Creates a consultation record.
        Business rules enforced:
        - Only the assigned doctor can create a consultation
        - Appointment must be in_progress or completed
        - Appointment must not already have a consultation
        - doctor and created_by are set automatically
        """
        appointment = validated_data.get('appointment')

        # Only the assigned doctor can create a consultation
        if requesting_user.role == 'doctor' and appointment.doctor != requesting_user:
            raise ValueError(
                "You can only create consultations for your own appointments."
            )

        # Appointment must be in a valid state
        if appointment.status not in ['in_progress', 'completed']:
            raise ValueError(
                f"Cannot create a consultation for an appointment "
                f"with status '{appointment.status}'. "
                f"Appointment must be in_progress or completed."
            )

        # No duplicate consultations
        if Consultation.objects.filter(
            appointment=appointment,
            deleted_at__isnull=True
        ).exists():
            raise ValueError("This appointment already has a consultation record.")

        return Consultation.objects.create(
            **validated_data,
            doctor=appointment.doctor,      # Set directly from appointment
            created_by=requesting_user,
            updated_by=requesting_user,
        )

    @staticmethod
    def update_consultation(consultation_id, validated_data, requesting_user):
        """
        Updates a draft consultation.
        Business rules enforced:
        - Cannot update a finalized consultation
        - Only the assigned doctor can update
        - updated_by is stamped automatically
        """
        consultation = Consultation.objects.filter(
            id=consultation_id,
            deleted_at__isnull=True
        ).first()

        if not consultation:
            raise ValueError("Consultation not found.")

        if consultation.status == 'finalized':
            raise ValueError(
                "Cannot update a finalized consultation. "
                "Finalized records are locked."
            )

        if requesting_user.role == 'doctor' and consultation.doctor != requesting_user:
            raise ValueError(
                "You can only update your own consultations."
            )

        for field, value in validated_data.items():
            setattr(consultation, field, value)

        consultation.updated_by = requesting_user
        consultation.save()
        return consultation

    @staticmethod
    def finalize_consultation(consultation_id, requesting_user):
        """
        Finalizes a consultation, locking it from further edits.
        Business rules enforced:
        - Only the assigned doctor can finalize
        - Must be in draft status
        - Must have at least one prescription before finalizing
        """
        consultation = Consultation.objects.filter(
            id=consultation_id,
            deleted_at__isnull=True
        ).prefetch_related('prescriptions').first()

        if not consultation:
            raise ValueError("Consultation not found.")

        if consultation.status != 'draft':
            raise ValueError(
                f"Cannot finalize a consultation with status '{consultation.status}'."
            )

        if requesting_user.role == 'doctor' and consultation.doctor != requesting_user:
            raise ValueError("You can only finalize your own consultations.")

        # Must have at least a diagnosis before finalizing
        if not consultation.diagnosis.strip():
            raise ValueError(
                "Cannot finalize a consultation without a diagnosis."
            )

        consultation.status = 'finalized'
        consultation.updated_by = requesting_user
        consultation.save()
        return consultation

    @staticmethod
    def list_consultations(requesting_user):
        """
        Returns consultations scoped to the requesting user's role.
        - Doctors only see their own consultations
        - Admins and receptionists see all
        Receptionists get limited data via the serializer layer.
        """
        queryset = Consultation.objects.filter(
            deleted_at__isnull=True
        ).select_related(
            'appointment__patient',
            'doctor',
            'created_by',
            'updated_by'
        ).order_by('-created_at')

        if requesting_user.role == 'doctor':
            return queryset.filter(doctor=requesting_user)

        return queryset

    @staticmethod
    def get_consultation_by_id(consultation_id):
        """
        Retrieves a single active consultation.
        Returns None if not found or soft deleted.
        """
        return Consultation.objects.filter(
            id=consultation_id,
            deleted_at__isnull=True
        ).select_related(
            'appointment__patient',
            'doctor',
            'created_by',
            'updated_by'
        ).first()

    @staticmethod
    def soft_delete_consultation(consultation_id, requesting_user):
        """
        Soft deletes a consultation.
        Business rules enforced:
        - Cannot delete a finalized consultation
        - Doctors can only delete their own consultations
        - Admins can delete any consultation
        Raises ValueError so the view can respond with correct HTTP status.
        """
        consultation = Consultation.objects.filter(
            id=consultation_id,
            deleted_at__isnull=True
        ).first()

        if not consultation:
            raise ValueError("Consultation not found.")

        if consultation.status == 'finalized':
            raise ValueError(
                "Cannot delete a finalized consultation. "
                "Finalized records are permanent."
            )

        if requesting_user.role == 'receptionist':
            raise ValueError("Receptionists cannot delete consultations.")

        if requesting_user.role == 'doctor' and consultation.doctor != requesting_user:
            raise ValueError("You can only delete your own consultations.")

        consultation.deleted_at = timezone.now()
        consultation.updated_by = requesting_user
        consultation.save()
        return consultation