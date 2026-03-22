"""
ViewSet / API tests for PrescriptionViewSet.

Tests make real HTTP requests and verify:
  - Correct HTTP status codes per action and role
  - Response shape differences per role (doctor/admin/receptionist)
  - Permission enforcement at the API boundary
  - Status transition endpoint behaviour
  - Business rule violations return 400, not 500

Test groups:
    TestPrescriptionList            → GET /prescriptions/
    TestPrescriptionRetrieve        → GET /prescriptions/{id}/
    TestPrescriptionCreate          → POST /prescriptions/
    TestPrescriptionUpdate          → PATCH /prescriptions/{id}/
    TestPrescriptionStatusUpdate    → PATCH /prescriptions/{id}/status/
    TestPrescriptionDelete          → DELETE /prescriptions/{id}/
"""

from rest_framework import status
from .base import PrescriptionTestBase


# ==========================================================================
# LIST
# ==========================================================================

class TestPrescriptionList(PrescriptionTestBase):

    def test_doctor_can_list_prescriptions(self):
        self.auth(self.doctor)
        response = self.client.get(self.PRESCRIPTIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_doctor_only_sees_own_prescriptions_in_list(self):
        """Doctor list is scoped — other doctors' prescriptions are hidden."""
        other_appt = self._make_appointment(self.other_doctor, self.patient)
        other_consultation = self._make_consultation(other_appt, self.other_doctor)
        self._make_prescription(other_consultation, self.other_doctor, medication_name='Drug B')

        self.auth(self.doctor)
        response = self.client.get(self.PRESCRIPTIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        ids = [p['id'] for p in response.data]
        self.assertIn(self.prescription.id, ids)
        self.assertEqual(len(ids), 1)

    def test_admin_sees_all_prescriptions(self):
        other_appt = self._make_appointment(self.other_doctor, self.patient)
        other_consultation = self._make_consultation(other_appt, self.other_doctor)
        self._make_prescription(other_consultation, self.other_doctor, medication_name='Drug B')

        self.auth(self.admin)
        response = self.client.get(self.PRESCRIPTIONS_URL)
        self.assertGreaterEqual(len(response.data), 2)

    def test_receptionist_can_list_but_sees_limited_fields(self):
        """Receptionist sees medication_name and status but not dosage/frequency/etc."""
        self.auth(self.receptionist)
        response = self.client.get(self.PRESCRIPTIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for item in response.data:
            self.assertIn('medication_name', item)
            self.assertIn('status', item)
            self.assertNotIn('dosage', item)
            self.assertNotIn('frequency', item)
            self.assertNotIn('duration', item)
            self.assertNotIn('instructions', item)

    def test_unauthenticated_cannot_list(self):
        self.clear_auth()
        response = self.client.get(self.PRESCRIPTIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_status(self):
        self.auth(self.doctor)
        response = self.client.get(self.PRESCRIPTIONS_URL, {'status': 'active'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data:
            self.assertEqual(item['status'], 'active')

    def test_filter_by_patient(self):
        self.auth(self.admin)
        response = self.client.get(self.PRESCRIPTIONS_URL, {'patient': self.patient.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data:
            self.assertEqual(item['patient_name'], 'John Doe')

    def test_filter_by_consultation(self):
        self.auth(self.doctor)
        response = self.client.get(
            self.PRESCRIPTIONS_URL, {'consultation': self.consultation.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data:
            self.assertEqual(item['consultation_id'], self.consultation.id)


# ==========================================================================
# RETRIEVE
# ==========================================================================

class TestPrescriptionRetrieve(PrescriptionTestBase):

    def test_doctor_can_retrieve_own_prescription(self):
        self.auth(self.doctor)
        response = self.client.get(self.prescription_url(self.prescription.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.prescription.id)

    def test_doctor_cannot_retrieve_other_doctors_prescription(self):
        other_appt = self._make_appointment(self.other_doctor, self.patient)
        other_consultation = self._make_consultation(other_appt, self.other_doctor)
        other_prescription = self._make_prescription(
            other_consultation, self.other_doctor, medication_name='Drug B'
        )
        self.auth(self.doctor)
        response = self.client.get(self.prescription_url(other_prescription.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_retrieve_any_prescription(self):
        self.auth(self.admin)
        response = self.client.get(self.prescription_url(self.prescription.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_response_includes_audit_fields(self):
        self.auth(self.admin)
        response = self.client.get(self.prescription_url(self.prescription.id))
        self.assertIn('created_by_name', response.data)
        self.assertIn('updated_by_name', response.data)

    def test_doctor_response_includes_clinical_fields(self):
        self.auth(self.doctor)
        response = self.client.get(self.prescription_url(self.prescription.id))
        self.assertIn('dosage', response.data)
        self.assertIn('frequency', response.data)
        self.assertIn('duration', response.data)
        self.assertIn('instructions', response.data)

    def test_receptionist_response_excludes_clinical_fields(self):
        self.auth(self.receptionist)
        response = self.client.get(self.prescription_url(self.prescription.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('dosage', response.data)
        self.assertNotIn('frequency', response.data)
        self.assertNotIn('duration', response.data)
        self.assertNotIn('instructions', response.data)

    def test_retrieve_nonexistent_returns_404(self):
        self.auth(self.doctor)
        response = self.client.get(self.prescription_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ==========================================================================
# CREATE
# ==========================================================================

class TestPrescriptionCreate(PrescriptionTestBase):

    def _fresh_consultation(self, doctor=None):
        appt = self._make_appointment(doctor or self.doctor, self.patient)
        return self._make_consultation(appt, doctor or self.doctor)

    def test_assigned_doctor_can_create(self):
        consultation = self._fresh_consultation()
        self.auth(self.doctor)
        response = self.client.post(self.PRESCRIPTIONS_URL, {
            'consultation': consultation.id,
            'medication_name': 'Paracetamol',
            'dosage': '1000mg',
            'frequency': 'Three times daily',
            'duration': '3 days',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'active')
        self.assertEqual(response.data['medication_name'], 'Paracetamol')

    def test_wrong_doctor_cannot_create(self):
        consultation = self._fresh_consultation(doctor=self.doctor)
        self.auth(self.other_doctor)
        response = self.client.post(self.PRESCRIPTIONS_URL, {
            'consultation': consultation.id,
            'medication_name': 'Ibuprofen',
            'dosage': '400mg',
            'frequency': 'Twice daily',
            'duration': '5 days',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receptionist_cannot_create(self):
        consultation = self._fresh_consultation()
        self.auth(self.receptionist)
        response = self.client.post(self.PRESCRIPTIONS_URL, {
            'consultation': consultation.id,
            'medication_name': 'Metformin',
            'dosage': '500mg',
            'frequency': 'Once daily',
            'duration': '30 days',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_create(self):
        """Admins don't create clinical records."""
        consultation = self._fresh_consultation()
        self.auth(self.admin)
        response = self.client.post(self.PRESCRIPTIONS_URL, {
            'consultation': consultation.id,
            'medication_name': 'Aspirin',
            'dosage': '100mg',
            'frequency': 'Once daily',
            'duration': '14 days',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_create_for_finalized_consultation(self):
        self.consultation.status = 'finalized'
        self.consultation.save()

        self.auth(self.doctor)
        response = self.client.post(self.PRESCRIPTIONS_URL, {
            'consultation': self.consultation.id,
            'medication_name': 'Drug X',
            'dosage': '100mg',
            'frequency': 'Once daily',
            'duration': '5 days',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blank_medication_name_rejected(self):
        consultation = self._fresh_consultation()
        self.auth(self.doctor)
        response = self.client.post(self.PRESCRIPTIONS_URL, {
            'consultation': consultation.id,
            'medication_name': '   ',
            'dosage': '100mg',
            'frequency': 'Once daily',
            'duration': '5 days',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_create(self):
        self.clear_auth()
        response = self.client.post(self.PRESCRIPTIONS_URL, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==========================================================================
# UPDATE
# ==========================================================================

class TestPrescriptionUpdate(PrescriptionTestBase):

    def test_assigned_doctor_can_update_active_prescription(self):
        self.auth(self.doctor)
        response = self.client.patch(
            self.prescription_url(self.prescription.id),
            {'dosage': '250mg'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dosage'], '250mg')

    def test_other_doctor_cannot_update(self):
        self.auth(self.other_doctor)
        response = self.client.patch(
            self.prescription_url(self.prescription.id),
            {'dosage': '250mg'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_update_completed_prescription(self):
        self.prescription.status = 'completed'
        self.prescription.save()

        self.auth(self.doctor)
        response = self.client.patch(
            self.prescription_url(self.prescription.id),
            {'dosage': '250mg'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_update_on_finalized_consultation(self):
        self.consultation.status = 'finalized'
        self.consultation.save()

        self.auth(self.doctor)
        response = self.client.patch(
            self.prescription_url(self.prescription.id),
            {'dosage': '250mg'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receptionist_cannot_update(self):
        self.auth(self.receptionist)
        response = self.client.patch(
            self.prescription_url(self.prescription.id),
            {'dosage': '250mg'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ==========================================================================
# STATUS UPDATE
# ==========================================================================

class TestPrescriptionStatusUpdate(PrescriptionTestBase):

    def test_doctor_can_mark_as_completed(self):
        self.auth(self.doctor)
        response = self.client.patch(
            self.status_url(self.prescription.id),
            {'status': 'completed'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')

    def test_doctor_can_mark_as_cancelled(self):
        self.auth(self.doctor)
        response = self.client.patch(
            self.status_url(self.prescription.id),
            {'status': 'cancelled'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'cancelled')

    def test_admin_can_update_status(self):
        """Admin can change status on any prescription."""
        self.auth(self.admin)
        response = self.client.patch(
            self.status_url(self.prescription.id),
            {'status': 'completed'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_doctor_cannot_update_status(self):
        self.auth(self.other_doctor)
        response = self.client.patch(
            self.status_url(self.prescription.id),
            {'status': 'completed'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receptionist_cannot_update_status(self):
        """Receptionist passes IsAuthenticated but is blocked by the service layer."""
        self.auth(self.receptionist)
        response = self.client.patch(
            self.status_url(self.prescription.id),
            {'status': 'completed'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_transition_from_completed_returns_400(self):
        self.prescription.status = 'completed'
        self.prescription.save()

        self.auth(self.doctor)
        response = self.client.patch(
            self.status_url(self.prescription.id),
            {'status': 'cancelled'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_transition_from_cancelled_returns_400(self):
        self.prescription.status = 'cancelled'
        self.prescription.save()

        self.auth(self.doctor)
        response = self.client.patch(
            self.status_url(self.prescription.id),
            {'status': 'active'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_status_value_returns_400(self):
        self.auth(self.doctor)
        response = self.client.patch(
            self.status_url(self.prescription.id),
            {'status': 'suspended'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_status_update_nonexistent_returns_404(self):
        self.auth(self.doctor)
        response = self.client.patch(
            self.status_url(99999),
            {'status': 'completed'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ==========================================================================
# DELETE
# ==========================================================================

class TestPrescriptionDelete(PrescriptionTestBase):

    def test_assigned_doctor_can_soft_delete_active_prescription(self):
        self.auth(self.doctor)
        response = self.client.delete(self.prescription_url(self.prescription.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Confirm it no longer appears
        self.auth(self.doctor)
        get_response = self.client.get(self.prescription_url(self.prescription.id))
        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_delete_any_active_prescription(self):
        self.auth(self.admin)
        response = self.client.delete(self.prescription_url(self.prescription.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_doctor_cannot_delete(self):
        self.auth(self.other_doctor)
        response = self.client.delete(self.prescription_url(self.prescription.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_delete_completed_prescription(self):
        self.prescription.status = 'completed'
        self.prescription.save()

        self.auth(self.doctor)
        response = self.client.delete(self.prescription_url(self.prescription.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_delete_cancelled_prescription(self):
        """Cancelled is not terminal for deletion — allowed."""
        self.prescription.status = 'cancelled'
        self.prescription.save()

        self.auth(self.doctor)
        response = self.client.delete(self.prescription_url(self.prescription.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cannot_delete_on_finalized_consultation(self):
        self.consultation.status = 'finalized'
        self.consultation.save()

        self.auth(self.doctor)
        response = self.client.delete(self.prescription_url(self.prescription.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receptionist_cannot_delete(self):
        self.auth(self.receptionist)
        response = self.client.delete(self.prescription_url(self.prescription.id))
        # Receptionist passes IsAdminDoctorOrReceptionist but service blocks them.
        # This assumes you add the same receptionist guard to PrescriptionService
        # as we added to ConsultationService. If not yet added, this will be 200.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_nonexistent_returns_400(self):
        self.auth(self.doctor)
        response = self.client.delete(self.prescription_url(99999))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)