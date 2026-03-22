from apps.patients.models import Patient
from apps.consultations.models import Consultation
from apps.appointments.models import Appointment
from django.db.models import Prefetch
from apps.prescriptions.models import Prescription


class MedicalRecordService:
    """
    Read-only aggregation service for patient medical records.

    This service never writes to the database.
    Its sole responsibility is fetching and assembling a
    structured, complete medical history for a given patient.

    Access rules enforced here:
    - Patient must exist and not be soft deleted
    - Doctors can only access records of patients they have
      had at least one appointment with
    - Admins and receptionists can access any patient's record
      (receptionists get limited data via the serializer layer)
    """

    @staticmethod
    def _verify_patient(patient_id):
        """
        Fetches an active patient or raises ValueError.
        Never uses get_object_or_404 — that is a view concern.
        """
        patient = Patient.objects.filter(
            id=patient_id,
            deleted_at__isnull=True
        ).first()

        if not patient:
            raise ValueError("Patient not found.")

        return patient

    @staticmethod
    def _check_access(requesting_user, patient):
        """
        Enforces role-based access to medical records.

        Doctors may only access records of patients they have
        had at least one appointment with — completed or otherwise.
        This prevents doctors from browsing arbitrary patient records.

        Admins and receptionists have full access.
        Receptionists receive restricted data via the serializer.
        """
        if requesting_user.is_superuser:
            return  # Admin — full access

        if requesting_user.role == 'receptionist':
            return  # Receptionist — access granted, data restricted at serializer level

        if requesting_user.role == 'doctor':
            has_appointment = Appointment.objects.filter(
                doctor=requesting_user,
                patient=patient,
                deleted_at__isnull=True
            ).exists()

            if not has_appointment:
                raise ValueError(
                    "Access denied. You can only view records of "
                    "patients you have had appointments with."
                )

            return

        # Any other role — deny by default
        raise ValueError("You do not have permission to access medical records.")

    @staticmethod
    def get_patient_medical_record(requesting_user, patient_id):
        """
        Fetches a patient's full medical history.

        Returns a structured dict containing:
        - patient: Patient instance
        - consultations: Queryset of consultations with
                         prefetched active prescriptions
                         ordered by most recent first

        Only includes:
        - Active (non soft-deleted) consultations
        - Active (non soft-deleted) prescriptions
        - Finalized consultations only for doctors
          (doctors should not see another doctor's drafts)
        """
        patient = MedicalRecordService._verify_patient(patient_id)
        MedicalRecordService._check_access(requesting_user, patient)

        # Build the prescription prefetch — only active, non-deleted prescriptions
        active_prescriptions = Prescription.objects.filter(
            deleted_at__isnull=True
        ).order_by('medication_name')

        # Base consultation queryset — only non-deleted consultations
        consultation_qs = Consultation.objects.filter(
            appointment__patient=patient,
            deleted_at__isnull=True
        ).select_related(
            'appointment',
            'appointment__doctor',
            'created_by',
        ).prefetch_related(
            Prefetch(
                'prescriptions',
                queryset=active_prescriptions
            )
        ).order_by('-created_at')

        # Doctors only see finalized consultations
        # They should not see draft consultations from other doctors
        if requesting_user.role == 'doctor':
            consultation_qs = consultation_qs.filter(
                status='finalized'
            )

        return {
            'patient': patient,
            'consultations': consultation_qs,
        }

    @staticmethod
    def get_patient_prescription_history(requesting_user, patient_id):
        """
        Fetches all active prescriptions for a patient.
        Useful for a quick medication overview without
        loading the full consultation history.

        Same access rules apply as get_patient_medical_record.
        """
        patient = MedicalRecordService._verify_patient(patient_id)
        MedicalRecordService._check_access(requesting_user, patient)

        prescriptions = Prescription.objects.filter(
            patient=patient,
            deleted_at__isnull=True
        ).select_related(
            'consultation__appointment__doctor',
            'created_by',
        ).order_by('-created_at')

        if requesting_user.role == 'doctor':
            prescriptions = prescriptions.filter(
                consultation__appointment__doctor=requesting_user
            )

        return {
            'patient': patient,
            'prescriptions': prescriptions,
        }