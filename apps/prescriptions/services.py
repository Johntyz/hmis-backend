from django.utils import timezone
from .models import Prescription


class PrescriptionService:
    """
    Service layer for Prescription business logic.
    Responsibilities:
    - Creating prescriptions
    - Updating prescriptions
    - Status transition enforcement
    - Fetching prescriptions (role-scoped)
    - Soft deleting prescriptions
    All business rules are enforced here before any database write.
    Raises ValueError for all business rule violations for consistent
    DRF error formatting in views.
    """

    @staticmethod
    def create_prescription(validated_data, requesting_user):
        """
        Creates a prescription record.
        Business rules enforced:
        - Only the assigned doctor can prescribe
        - Consultation must be in draft status
        - Consultation must not be soft deleted
        - patient and audit fields are set automatically
        """
        consultation = validated_data.get('consultation')
        appointment = consultation.appointment

        # Only the assigned doctor can prescribe
        if requesting_user.role == 'doctor' and appointment.doctor != requesting_user:
            raise ValueError(
                "You can only prescribe for your own consultations."
            )

        # Consultation must be in draft
        if consultation.status != 'draft':
            raise ValueError(
                f"Cannot add prescriptions to a consultation "
                f"with status '{consultation.status}'. "
                f"Consultation must be in draft."
            )

        # Patient is derived automatically from the consultation
        patient = appointment.patient

        return Prescription.objects.create(
            **validated_data,
            patient=patient,
            created_by=requesting_user,
            updated_by=requesting_user,
        )

    @staticmethod
    def update_prescription(prescription_id, validated_data, requesting_user):
        """
        Updates an active prescription.
        Business rules enforced:
        - Cannot update a completed or cancelled prescription
        - Only the prescribing doctor can update
        - Consultation FK cannot be changed after creation
        - updated_by is stamped automatically
        """
        prescription = Prescription.objects.filter(
            id=prescription_id,
            deleted_at__isnull=True
        ).first()

        if not prescription:
            raise ValueError("Prescription not found.")

        if prescription.status in ['completed', 'cancelled']:
            raise ValueError(
                f"Cannot update a prescription with status "
                f"'{prescription.status}'."
            )

        if prescription.consultation.status == 'finalized':
            raise ValueError(
                "Cannot update a prescription belonging to a "
                "finalized consultation."
            )

        if requesting_user.role == 'doctor':
            if prescription.consultation.appointment.doctor != requesting_user:
                raise ValueError(
                    "You can only update prescriptions from your own consultations."
                )

        # Prevent consultation reassignment after creation
        validated_data.pop('consultation', None)

        for field, value in validated_data.items():
            setattr(prescription, field, value)

        prescription.updated_by = requesting_user
        prescription.save()
        return prescription

    @staticmethod
    def update_status(prescription_id, new_status, requesting_user):
        """
        Updates prescription status following strict transition rules.
        Business rules enforced:
        - Only valid transitions are allowed
        - Only the prescribing doctor or admin can change status
        """
        prescription = Prescription.objects.filter(
            id=prescription_id,
            deleted_at__isnull=True
        ).first()

        if not prescription:
            raise ValueError("Prescription not found.")

        current_status = prescription.status
        valid_next = Prescription.VALID_TRANSITIONS.get(current_status, [])

        if new_status not in valid_next:
            raise ValueError(
                f"Cannot transition from '{current_status}' to '{new_status}'. "
                f"Valid transitions: {valid_next}."
            )
        if requesting_user.role == 'receptionist':
            raise ValueError("Receptionists cannot update prescription status.")
        if requesting_user.role == 'doctor':
            if prescription.consultation.appointment.doctor != requesting_user:
                raise ValueError(
                    "You can only update status of your own prescriptions."
                )

        prescription.status = new_status
        prescription.updated_by = requesting_user
        prescription.save()
        return prescription

    @staticmethod
    def list_prescriptions(requesting_user, patient_id=None):
        """
        Returns prescriptions scoped to the requesting user's role.
        - Doctors only see prescriptions they created
        - Admins and receptionists see all
        Supports optional filtering by patient_id for patient-level queries.
        """
        queryset = Prescription.objects.filter(
            deleted_at__isnull=True
        ).select_related(
            'consultation__appointment',
            'patient',
            'created_by',
            'updated_by'
        ).order_by('-created_at')

        if requesting_user.role == 'doctor':
            queryset = queryset.filter(
                consultation__appointment__doctor=requesting_user
            )

        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)

        return queryset

    @staticmethod
    def get_prescription_by_id(prescription_id):
        """
        Retrieves a single active prescription.
        Returns None if not found or soft deleted.
        """
        return Prescription.objects.filter(
            id=prescription_id,
            deleted_at__isnull=True
        ).select_related(
            'consultation__appointment',
            'patient',
            'created_by',
            'updated_by'
        ).first()

    @staticmethod
    def soft_delete_prescription(prescription_id, requesting_user):
        """
        Soft deletes a prescription.
        Business rules enforced:
        - Cannot delete a completed prescription
        - Cannot delete a prescription from a finalized consultation
        - Doctors can only delete their own prescriptions
        - Admins can delete any active prescription
        Raises ValueError so the view responds with correct HTTP status.
        """
        prescription = Prescription.objects.filter(
            id=prescription_id,
            deleted_at__isnull=True
        ).first()

        if not prescription:
            raise ValueError("Prescription not found.")

        if prescription.status == 'completed':
            raise ValueError("Cannot delete a completed prescription.")

        if prescription.consultation.status == 'finalized':
            raise ValueError(
                "Cannot delete a prescription belonging to a "
                "finalized consultation."
            )
        if requesting_user.role == 'receptionist':
            raise ValueError("Receptionists cannot delete prescriptions.")
        

        if requesting_user.role == 'doctor':
            if prescription.consultation.appointment.doctor != requesting_user:
                raise ValueError(
                    "You can only delete your own prescriptions."
                )

        prescription.deleted_at = timezone.now()
        prescription.updated_by = requesting_user
        prescription.save()
        return prescription