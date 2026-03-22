"""
API tests for PatientMedicalRecordView and PatientPrescriptionHistoryView.

Both views are GET-only. Tests verify:
  - Correct HTTP status codes per role
  - Response structure (patient block, consultations/prescriptions block)
  - Clinical data privacy (receptionists never see diagnosis/dosage)
  - Access control (doctor blocked without appointment history)
  - Edge cases (soft deleted patient, no history)

Test groups:
    TestMedicalRecordView           → GET /patients/{id}/medical-records/
    TestPrescriptionHistoryView     → GET /patients/{id}/prescription-history/
"""

from rest_framework import status
from .base import MedicalRecordTestBase


# ==========================================================================
# MEDICAL RECORD VIEW
# ==========================================================================

class TestMedicalRecordView(MedicalRecordTestBase):

    # --- Access ---

    def test_unauthenticated_cannot_access(self):
        self.clear_auth()
        response = self.client.get(self.medical_record_url(self.patient.id))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_access(self):
        self.auth(self.admin)
        response = self.client.get(self.medical_record_url(self.patient.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_doctor_with_appointment_can_access(self):
        self.auth(self.doctor)
        response = self.client.get(self.medical_record_url(self.patient.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_doctor_without_appointment_is_denied(self):
        """other_doctor has no appointment with self.patient."""
        self.auth(self.other_doctor)
        response = self.client.get(self.medical_record_url(self.patient.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_receptionist_can_access(self):
        self.auth(self.receptionist)
        response = self.client.get(self.medical_record_url(self.patient.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nonexistent_patient_returns_404(self):
        self.auth(self.admin)
        response = self.client.get(self.medical_record_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Response structure ---

    def test_response_contains_patient_block(self):
        self.auth(self.admin)
        response = self.client.get(self.medical_record_url(self.patient.id))
        self.assertIn('patient', response.data)
        self.assertEqual(response.data['patient']['id'], self.patient.id)

    def test_response_contains_consultations_and_total(self):
        self.auth(self.admin)
        response = self.client.get(self.medical_record_url(self.patient.id))
        self.assertIn('consultations', response.data)
        self.assertIn('total_consultations', response.data)

    def test_patient_block_includes_demographics(self):
        self.auth(self.admin)
        response = self.client.get(self.medical_record_url(self.patient.id))
        patient_data = response.data['patient']
        self.assertIn('full_name', patient_data)
        self.assertIn('date_of_birth', patient_data)
        self.assertIn('gender', patient_data)
        self.assertIn('phone_number', patient_data)

    def test_total_consultations_is_accurate(self):
        self.auth(self.admin)
        response = self.client.get(self.medical_record_url(self.patient.id))
        self.assertEqual(response.data['total_consultations'], 1)

    # --- Clinical data privacy ---

    def test_doctor_response_includes_clinical_fields(self):
        self.auth(self.doctor)
        response = self.client.get(self.medical_record_url(self.patient.id))
        consultations = response.data['consultations']
        self.assertTrue(len(consultations) > 0)
        for c in consultations:
            self.assertIn('diagnosis', c)
            self.assertIn('notes', c)

    def test_receptionist_response_excludes_diagnosis_and_notes(self):
        self.auth(self.receptionist)
        response = self.client.get(self.medical_record_url(self.patient.id))
        for c in response.data['consultations']:
            self.assertNotIn('diagnosis', c)
            self.assertNotIn('notes', c)

    def test_doctor_sees_full_prescription_details(self):
        self.auth(self.doctor)
        response = self.client.get(self.medical_record_url(self.patient.id))
        for c in response.data['consultations']:
            for p in c['prescriptions']:
                self.assertIn('dosage', p)
                self.assertIn('frequency', p)
                self.assertIn('duration', p)
                self.assertIn('instructions', p)

    def test_receptionist_sees_restricted_prescription_fields(self):
        """Receptionists see medication_name and status only — no clinical dosage."""
        self.auth(self.receptionist)
        response = self.client.get(self.medical_record_url(self.patient.id))
        for c in response.data['consultations']:
            for p in c['prescriptions']:
                self.assertIn('medication_name', p)
                self.assertIn('status', p)
                self.assertNotIn('dosage', p)
                self.assertNotIn('frequency', p)
                self.assertNotIn('instructions', p)

    # --- Doctor scoping ---

    def test_doctor_only_sees_finalized_consultations(self):
        """Draft consultations must not appear in a doctor's view."""
        draft_appt = self._make_appointment(self.doctor, self.patient)
        draft_consultation = self._make_consultation(
            draft_appt, self.doctor, status='draft'
        )

        self.auth(self.doctor)
        response = self.client.get(self.medical_record_url(self.patient.id))

        consultation_ids = [c['id'] for c in response.data['consultations']]
        self.assertIn(self.consultation.id, consultation_ids)
        self.assertNotIn(draft_consultation.id, consultation_ids)

    def test_admin_sees_draft_and_finalized_consultations(self):
        draft_appt = self._make_appointment(self.doctor, self.patient)
        draft_consultation = self._make_consultation(
            draft_appt, self.doctor, status='draft'
        )

        self.auth(self.admin)
        response = self.client.get(self.medical_record_url(self.patient.id))

        consultation_ids = [c['id'] for c in response.data['consultations']]
        self.assertIn(self.consultation.id, consultation_ids)
        self.assertIn(draft_consultation.id, consultation_ids)

    # --- Edge cases ---

    def test_patient_with_no_history_returns_empty_consultations(self):
        empty_patient = self._make_patient(
            first_name='Empty', last_name='Patient',
            phone='0700000002', email='empty@hmis.test'
        )
        self.auth(self.admin)
        response = self.client.get(self.medical_record_url(empty_patient.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_consultations'], 0)
        self.assertEqual(response.data['consultations'], [])

    def test_soft_deleted_consultation_not_in_response(self):
        from django.utils import timezone
        self.consultation.deleted_at = timezone.now()
        self.consultation.save()

        self.auth(self.admin)
        response = self.client.get(self.medical_record_url(self.patient.id))
        consultation_ids = [c['id'] for c in response.data['consultations']]
        self.assertNotIn(self.consultation.id, consultation_ids)


# ==========================================================================
# PRESCRIPTION HISTORY VIEW
# ==========================================================================

class TestPrescriptionHistoryView(MedicalRecordTestBase):

    # --- Access ---

    def test_unauthenticated_cannot_access(self):
        self.clear_auth()
        response = self.client.get(self.prescription_history_url(self.patient.id))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_access(self):
        self.auth(self.admin)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_doctor_with_appointment_can_access(self):
        self.auth(self.doctor)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_doctor_without_appointment_is_denied(self):
        self.auth(self.other_doctor)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_receptionist_can_access(self):
        self.auth(self.receptionist)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nonexistent_patient_returns_404(self):
        self.auth(self.admin)
        response = self.client.get(self.prescription_history_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Response structure ---

    def test_response_contains_patient_and_prescriptions(self):
        self.auth(self.admin)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        self.assertIn('patient', response.data)
        self.assertIn('prescriptions', response.data)
        self.assertIn('total_prescriptions', response.data)

    def test_total_prescriptions_is_accurate(self):
        self.auth(self.admin)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        self.assertEqual(response.data['total_prescriptions'], 1)

    def test_prescription_appears_in_response(self):
        self.auth(self.admin)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        prescription_ids = [p['id'] for p in response.data['prescriptions']]
        self.assertIn(self.prescription.id, prescription_ids)

    # --- Clinical data privacy ---

    def test_doctor_sees_full_prescription_details(self):
        self.auth(self.doctor)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        for p in response.data['prescriptions']:
            self.assertIn('dosage', p)
            self.assertIn('frequency', p)
            self.assertIn('duration', p)
            self.assertIn('instructions', p)

    def test_receptionist_sees_restricted_fields_only(self):
        self.auth(self.receptionist)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        for p in response.data['prescriptions']:
            self.assertIn('medication_name', p)
            self.assertIn('status', p)
            self.assertNotIn('dosage', p)
            self.assertNotIn('frequency', p)
            self.assertNotIn('instructions', p)

    def test_admin_sees_full_prescription_details(self):
        self.auth(self.admin)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        for p in response.data['prescriptions']:
            self.assertIn('dosage', p)
            self.assertIn('frequency', p)

    # --- Doctor scoping ---

    def test_doctor_only_sees_own_prescriptions(self):
        """Doctor prescription history is scoped to their own consultations."""
        other_appt = self._make_appointment(self.other_doctor, self.patient)
        other_consultation = self._make_consultation(other_appt, self.other_doctor)
        other_prescription = self._make_prescription(
            other_consultation, self.other_doctor, medication_name='Metformin'
        )

        # Give other_doctor access by linking them to the patient
        self.auth(self.other_doctor)
        response = self.client.get(self.prescription_history_url(self.patient.id))

        prescription_ids = [p['id'] for p in response.data['prescriptions']]
        self.assertIn(other_prescription.id, prescription_ids)
        self.assertNotIn(self.prescription.id, prescription_ids)

    def test_admin_sees_prescriptions_from_all_doctors(self):
        other_appt = self._make_appointment(self.other_doctor, self.patient)
        other_consultation = self._make_consultation(other_appt, self.other_doctor)
        other_prescription = self._make_prescription(
            other_consultation, self.other_doctor, medication_name='Metformin'
        )

        self.auth(self.admin)
        response = self.client.get(self.prescription_history_url(self.patient.id))

        prescription_ids = [p['id'] for p in response.data['prescriptions']]
        self.assertIn(self.prescription.id, prescription_ids)
        self.assertIn(other_prescription.id, prescription_ids)

    # --- Edge cases ---

    def test_soft_deleted_prescription_not_in_response(self):
        from django.utils import timezone
        self.prescription.deleted_at = timezone.now()
        self.prescription.save()

        self.auth(self.admin)
        response = self.client.get(self.prescription_history_url(self.patient.id))
        prescription_ids = [p['id'] for p in response.data['prescriptions']]
        self.assertNotIn(self.prescription.id, prescription_ids)

    def test_patient_with_no_prescriptions_returns_empty(self):
        empty_patient = self._make_patient(
            first_name='NoPrescription', last_name='Patient',
            phone='0700000003', email='noprescription@hmis.test'
        )
        self.auth(self.admin)
        response = self.client.get(self.prescription_history_url(empty_patient.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_prescriptions'], 0)
        self.assertEqual(response.data['prescriptions'], [])