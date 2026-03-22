"""
Service layer tests for MedicalRecordService.

Tests call service methods directly — no HTTP involved.
This module is read-only so there are no write business rules
to test. Instead tests focus on:
  - Access control (_check_access logic)
  - Correct data returned (scoping, filtering)
  - Edge cases (soft deleted, no history, unrelated doctor)

Test groups:
    TestVerifyPatient               → patient lookup
    TestCheckAccess                 → role-based access rules
    TestGetPatientMedicalRecord     → full medical history
    TestGetPatientPrescriptionHistory → prescription overview
"""

from django.utils import timezone
from apps.medical_records.services import MedicalRecordService
from .base import MedicalRecordTestBase


# ==========================================================================
# PATIENT VERIFICATION
# ==========================================================================

class TestVerifyPatient(MedicalRecordTestBase):

    def test_active_patient_is_returned(self):
        result = MedicalRecordService._verify_patient(self.patient.id)
        self.assertEqual(result.id, self.patient.id)

    def test_nonexistent_patient_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            MedicalRecordService._verify_patient(99999)
        self.assertIn('not found', str(ctx.exception).lower())

    def test_soft_deleted_patient_raises_error(self):
        self.patient.deleted_at = timezone.now()
        self.patient.save()

        with self.assertRaises(ValueError) as ctx:
            MedicalRecordService._verify_patient(self.patient.id)
        self.assertIn('not found', str(ctx.exception).lower())


# ==========================================================================
# ACCESS CONTROL
# ==========================================================================

class TestCheckAccess(MedicalRecordTestBase):

    def test_admin_can_access_any_patient(self):
        """Admins have unrestricted access — no exception raised."""
        try:
            MedicalRecordService._check_access(self.admin, self.patient)
        except ValueError:
            self.fail("Admin should not be blocked from accessing patient records.")

    def test_receptionist_can_access_any_patient(self):
        """Receptionists have access — data restriction happens at serializer level."""
        try:
            MedicalRecordService._check_access(self.receptionist, self.patient)
        except ValueError:
            self.fail("Receptionist should not be blocked from accessing patient records.")

    def test_doctor_with_appointment_can_access(self):
        """Doctor who has had an appointment with this patient gets access."""
        try:
            MedicalRecordService._check_access(self.doctor, self.patient)
        except ValueError:
            self.fail("Doctor with appointment should be able to access patient records.")

    def test_doctor_without_appointment_is_blocked(self):
        """other_doctor has no appointment with self.patient — must be denied."""
        with self.assertRaises(ValueError) as ctx:
            MedicalRecordService._check_access(self.other_doctor, self.patient)
        self.assertIn('Access denied', str(ctx.exception))

    def test_doctor_access_survives_cancelled_appointments(self):
        """Any appointment history — even cancelled — grants access."""
        cancelled_appt = self._make_appointment(
            self.other_doctor, self.patient, status='cancelled'
        )
        try:
            MedicalRecordService._check_access(self.other_doctor, self.patient)
        except ValueError:
            self.fail("Doctor with any appointment history should get access.")

    def test_doctor_access_denied_after_soft_deleting_appointment(self):
        """
        If a doctor's only appointment is soft-deleted, access is revoked.
        The service filters deleted_at__isnull=True on appointments.
        """
        # other_doctor gets an appointment, then it gets soft deleted
        appt = self._make_appointment(self.other_doctor, self.patient)
        appt.deleted_at = timezone.now()
        appt.save()

        with self.assertRaises(ValueError):
            MedicalRecordService._check_access(self.other_doctor, self.patient)


# ==========================================================================
# GET PATIENT MEDICAL RECORD
# ==========================================================================

class TestGetPatientMedicalRecord(MedicalRecordTestBase):

    def test_admin_gets_full_medical_record(self):
        result = MedicalRecordService.get_patient_medical_record(
            self.admin, self.patient.id
        )
        self.assertEqual(result['patient'].id, self.patient.id)
        self.assertIn('consultations', result)

    def test_doctor_with_appointment_gets_record(self):
        result = MedicalRecordService.get_patient_medical_record(
            self.doctor, self.patient.id
        )
        self.assertEqual(result['patient'].id, self.patient.id)

    def test_doctor_without_appointment_is_denied(self):
        with self.assertRaises(ValueError) as ctx:
            MedicalRecordService.get_patient_medical_record(
                self.other_doctor, self.patient.id
            )
        self.assertIn('Access denied', str(ctx.exception))

    def test_receptionist_gets_record(self):
        result = MedicalRecordService.get_patient_medical_record(
            self.receptionist, self.patient.id
        )
        self.assertEqual(result['patient'].id, self.patient.id)

    def test_nonexistent_patient_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            MedicalRecordService.get_patient_medical_record(self.admin, 99999)
        self.assertIn('not found', str(ctx.exception).lower())

    def test_doctor_only_sees_finalized_consultations(self):
        """
        Doctors must NOT see draft consultations — even from their own records.
        A draft consultation from setUp would be invisible.
        """
        # Add a draft consultation for the same doctor
        draft_appt = self._make_appointment(self.doctor, self.patient)
        draft_consultation = self._make_consultation(
            draft_appt, self.doctor, status='draft'
        )

        result = MedicalRecordService.get_patient_medical_record(
            self.doctor, self.patient.id
        )
        consultation_ids = list(
            result['consultations'].values_list('id', flat=True)
        )

        self.assertIn(self.consultation.id, consultation_ids)
        self.assertNotIn(draft_consultation.id, consultation_ids)

    def test_admin_sees_all_consultation_statuses(self):
        """Admins see both draft and finalized consultations."""
        draft_appt = self._make_appointment(self.doctor, self.patient)
        draft_consultation = self._make_consultation(
            draft_appt, self.doctor, status='draft'
        )

        result = MedicalRecordService.get_patient_medical_record(
            self.admin, self.patient.id
        )
        consultation_ids = list(
            result['consultations'].values_list('id', flat=True)
        )

        self.assertIn(self.consultation.id, consultation_ids)
        self.assertIn(draft_consultation.id, consultation_ids)

    def test_soft_deleted_consultations_are_excluded(self):
        self.consultation.deleted_at = timezone.now()
        self.consultation.save()

        result = MedicalRecordService.get_patient_medical_record(
            self.admin, self.patient.id
        )
        consultation_ids = list(
            result['consultations'].values_list('id', flat=True)
        )
        self.assertNotIn(self.consultation.id, consultation_ids)

    def test_prescriptions_are_prefetched_on_consultations(self):
        """Prescriptions appear nested under their consultation."""
        result = MedicalRecordService.get_patient_medical_record(
            self.admin, self.patient.id
        )
        consultation = result['consultations'].get(id=self.consultation.id)
        prescription_ids = [p.id for p in consultation.prescriptions.all()]
        self.assertIn(self.prescription.id, prescription_ids)

    def test_soft_deleted_prescriptions_excluded_from_record(self):
        """Soft deleted prescriptions must not appear in the medical record."""
        self.prescription.deleted_at = timezone.now()
        self.prescription.save()

        result = MedicalRecordService.get_patient_medical_record(
            self.admin, self.patient.id
        )
        consultation = result['consultations'].get(id=self.consultation.id)
        prescription_ids = [p.id for p in consultation.prescriptions.all()]
        self.assertNotIn(self.prescription.id, prescription_ids)

    def test_patient_with_no_consultations_returns_empty_list(self):
        empty_patient = self._make_patient(
            first_name='Empty', last_name='Patient',
            phone='0700000002', email='empty@hmis.test'
        )
        result = MedicalRecordService.get_patient_medical_record(
            self.admin, empty_patient.id
        )
        self.assertEqual(result['consultations'].count(), 0)


# ==========================================================================
# GET PATIENT PRESCRIPTION HISTORY
# ==========================================================================

class TestGetPatientPrescriptionHistory(MedicalRecordTestBase):

    def test_admin_gets_prescription_history(self):
        result = MedicalRecordService.get_patient_prescription_history(
            self.admin, self.patient.id
        )
        self.assertEqual(result['patient'].id, self.patient.id)
        prescription_ids = list(
            result['prescriptions'].values_list('id', flat=True)
        )
        self.assertIn(self.prescription.id, prescription_ids)

    def test_doctor_with_appointment_gets_own_prescriptions(self):
        """Doctor sees only prescriptions they wrote for this patient."""
        result = MedicalRecordService.get_patient_prescription_history(
            self.doctor, self.patient.id
        )
        for p in result['prescriptions']:
            self.assertEqual(p.consultation.appointment.doctor, self.doctor)

    def test_doctor_without_appointment_is_denied(self):
        with self.assertRaises(ValueError) as ctx:
            MedicalRecordService.get_patient_prescription_history(
                self.other_doctor, self.patient.id
            )
        self.assertIn('Access denied', str(ctx.exception))

    def test_receptionist_gets_prescription_history(self):
        result = MedicalRecordService.get_patient_prescription_history(
            self.receptionist, self.patient.id
        )
        self.assertEqual(result['patient'].id, self.patient.id)

    def test_soft_deleted_prescriptions_excluded(self):
        self.prescription.deleted_at = timezone.now()
        self.prescription.save()

        result = MedicalRecordService.get_patient_prescription_history(
            self.admin, self.patient.id
        )
        prescription_ids = list(
            result['prescriptions'].values_list('id', flat=True)
        )
        self.assertNotIn(self.prescription.id, prescription_ids)

    def test_nonexistent_patient_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            MedicalRecordService.get_patient_prescription_history(
                self.admin, 99999
            )
        self.assertIn('not found', str(ctx.exception).lower())

    def test_patient_with_no_prescriptions_returns_empty(self):
        empty_patient = self._make_patient(
            first_name='NoPrescription', last_name='Patient',
            phone='0700000003', email='noprescription@hmis.test'
        )
        result = MedicalRecordService.get_patient_prescription_history(
            self.admin, empty_patient.id
        )
        self.assertEqual(result['prescriptions'].count(), 0)

    def test_admin_sees_prescriptions_from_multiple_doctors(self):
        """Admin gets all prescriptions regardless of which doctor wrote them."""
        # Give other_doctor an appointment and prescription for this patient
        other_appt = self._make_appointment(self.other_doctor, self.patient)
        other_consultation = self._make_consultation(other_appt, self.other_doctor)
        other_prescription = self._make_prescription(
            other_consultation, self.other_doctor, medication_name='Metformin'
        )

        result = MedicalRecordService.get_patient_prescription_history(
            self.admin, self.patient.id
        )
        prescription_ids = list(
            result['prescriptions'].values_list('id', flat=True)
        )
        self.assertIn(self.prescription.id, prescription_ids)
        self.assertIn(other_prescription.id, prescription_ids)