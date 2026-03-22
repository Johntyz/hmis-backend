"""
ViewSet / API tests for ConsultationViewSet.

These tests make real HTTP requests through the DRF test client.
They verify:
  - Correct HTTP status codes per action and role
  - Response shape (fields present/absent by role)
  - Permission enforcement at the API boundary
  - Business rule violations return 400, not 500

Test groups:
    TestConsultationList        → GET /consultations/
    TestConsultationRetrieve    → GET /consultations/{id}/
    TestConsultationCreate      → POST /consultations/
    TestConsultationUpdate      → PATCH /consultations/{id}/
    TestConsultationFinalize    → PATCH /consultations/{id}/finalize/
    TestConsultationDelete      → DELETE /consultations/{id}/
    TestConsultationPermissions → Unauthenticated and wrong-role access
"""

from rest_framework import status
from .base import ConsultationTestBase


# ==========================================================================
# LIST
# ==========================================================================

class TestConsultationList(ConsultationTestBase):

    def test_doctor_can_list_consultations(self):
        self.auth(self.doctor)
        response = self.client.get(self.CONSULTATIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_doctor_only_sees_own_consultations_in_list(self):
        """Doctor list is scoped — other doctors' consultations are hidden."""
        # Give other_doctor their own consultation
        other_appt = self._make_appointment(
            doctor=self.other_doctor,
            patient=self.patient,
            status='in_progress',
        )
        self._make_consultation(appointment=other_appt, doctor=self.other_doctor)

        self.auth(self.doctor)
        response = self.client.get(self.CONSULTATIONS_URL)

        ids = [c['id'] for c in response.data]
        self.assertIn(self.consultation.id, ids)
        # other_doctor's consultation must NOT appear
        self.assertEqual(len(ids), 1)

    def test_admin_sees_all_consultations(self):
        other_appt = self._make_appointment(
            doctor=self.other_doctor,
            patient=self.patient,
            status='in_progress',
        )
        self._make_consultation(appointment=other_appt, doctor=self.other_doctor)

        self.auth(self.admin)
        response = self.client.get(self.CONSULTATIONS_URL)
        self.assertGreaterEqual(len(response.data), 2)

    def test_receptionist_can_list_but_no_clinical_fields(self):
        """Receptionist sees consultations but not diagnosis/notes/prescriptions."""
        self.auth(self.receptionist)
        response = self.client.get(self.CONSULTATIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for item in response.data:
            self.assertNotIn('diagnosis', item)
            self.assertNotIn('notes', item)
            self.assertNotIn('prescriptions', item)

    def test_unauthenticated_cannot_list(self):
        self.clear_auth()
        response = self.client.get(self.CONSULTATIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_filter_by_status(self):
        """?status=draft should return only draft consultations."""
        self.auth(self.doctor)
        response = self.client.get(self.CONSULTATIONS_URL, {'status': 'draft'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data:
            self.assertEqual(item['status'], 'draft')


# ==========================================================================
# RETRIEVE
# ==========================================================================

class TestConsultationRetrieve(ConsultationTestBase):

    def test_doctor_can_retrieve_own_consultation(self):
        self.auth(self.doctor)
        response = self.client.get(self.consultation_url(self.consultation.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.consultation.id)

    def test_doctor_cannot_retrieve_other_doctors_consultation(self):
        other_appt = self._make_appointment(
            doctor=self.other_doctor,
            patient=self.patient,
            status='in_progress',
        )
        other_consultation = self._make_consultation(
            appointment=other_appt,
            doctor=self.other_doctor,
        )
        self.auth(self.doctor)
        response = self.client.get(self.consultation_url(other_consultation.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_retrieve_any_consultation(self):
        self.auth(self.admin)
        response = self.client.get(self.consultation_url(self.consultation.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_response_includes_audit_fields(self):
        """Admin serializer exposes created_by_name and updated_by_name."""
        self.auth(self.admin)
        response = self.client.get(self.consultation_url(self.consultation.id))
        self.assertIn('created_by_name', response.data)
        self.assertIn('updated_by_name', response.data)

    def test_doctor_response_includes_clinical_fields(self):
        """Doctor serializer exposes diagnosis, notes, prescriptions."""
        self.auth(self.doctor)
        response = self.client.get(self.consultation_url(self.consultation.id))
        self.assertIn('diagnosis', response.data)
        self.assertIn('notes', response.data)
        self.assertIn('prescriptions', response.data)

    def test_receptionist_response_excludes_clinical_fields(self):
        """Receptionist serializer must never expose clinical data."""
        self.auth(self.receptionist)
        response = self.client.get(self.consultation_url(self.consultation.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('diagnosis', response.data)
        self.assertNotIn('notes', response.data)

    def test_retrieve_nonexistent_returns_404(self):
        self.auth(self.doctor)
        response = self.client.get(self.consultation_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ==========================================================================
# CREATE
# ==========================================================================

class TestConsultationCreate(ConsultationTestBase):

    def _fresh_appointment(self, doctor=None):
        """Helper — creates a new appointment with no consultation."""
        return self._make_appointment(
            doctor=doctor or self.doctor,
            patient=self.patient,
            status='in_progress',
        )

    def test_assigned_doctor_can_create(self):
        appt = self._fresh_appointment()
        self.auth(self.doctor)
        response = self.client.post(self.CONSULTATIONS_URL, {
            'appointment': appt.id,
            'diagnosis': 'Patient has a mild infection.',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'draft')

    def test_receptionist_cannot_create(self):
        appt = self._fresh_appointment()
        self.auth(self.receptionist)
        response = self.client.post(self.CONSULTATIONS_URL, {
            'appointment': appt.id,
            'diagnosis': 'Should not work.',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_create(self):
        """Admins manage staff — they don't create clinical records."""
        appt = self._fresh_appointment()
        self.auth(self.admin)
        response = self.client.post(self.CONSULTATIONS_URL, {
            'appointment': appt.id,
            'diagnosis': 'Admin should not do this.',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_wrong_doctor_cannot_create_for_others_appointment(self):
        """other_doctor cannot create a consultation for self.doctor's appointment."""
        appt = self._fresh_appointment(doctor=self.doctor)
        self.auth(self.other_doctor)
        response = self.client.post(self.CONSULTATIONS_URL, {
            'appointment': appt.id,
            'diagnosis': 'Unauthorized.',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_create_for_scheduled_appointment(self):
        appt = self._make_appointment(
            doctor=self.doctor,
            patient=self.patient,
            status='scheduled',
        )
        self.auth(self.doctor)
        response = self.client.post(self.CONSULTATIONS_URL, {
            'appointment': appt.id,
            'diagnosis': 'Too early.',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_create_duplicate_consultation(self):
        """self.appointment already has self.consultation from setUp."""
        self.auth(self.doctor)
        response = self.client.post(self.CONSULTATIONS_URL, {
            'appointment': self.appointment.id,
            'diagnosis': 'Duplicate attempt.',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_create(self):
        self.clear_auth()
        response = self.client.post(self.CONSULTATIONS_URL, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==========================================================================
# UPDATE
# ==========================================================================

class TestConsultationUpdate(ConsultationTestBase):

    def test_assigned_doctor_can_update_draft(self):
        self.auth(self.doctor)
        response = self.client.patch(
            self.consultation_url(self.consultation.id),
            {'diagnosis': 'Revised diagnosis after review.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['diagnosis'], 'Revised diagnosis after review.')

    def test_other_doctor_cannot_update(self):
        self.auth(self.other_doctor)
        response = self.client.patch(
            self.consultation_url(self.consultation.id),
            {'diagnosis': 'Unauthorized edit.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_update_finalized_consultation(self):
        self.consultation.status = 'finalized'
        self.consultation.save()

        self.auth(self.doctor)
        response = self.client.patch(
            self.consultation_url(self.consultation.id),
            {'diagnosis': 'Edit after lock.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receptionist_cannot_update(self):
        self.auth(self.receptionist)
        response = self.client.patch(
            self.consultation_url(self.consultation.id),
            {'diagnosis': 'No clinical access.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ==========================================================================
# FINALIZE
# ==========================================================================

class TestConsultationFinalize(ConsultationTestBase):

    def test_assigned_doctor_can_finalize(self):
        self.auth(self.doctor)
        response = self.client.patch(
            self.finalize_url(self.consultation.id),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'finalized')

    def test_other_doctor_cannot_finalize(self):
        self.auth(self.other_doctor)
        response = self.client.patch(
            self.finalize_url(self.consultation.id),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_finalize_already_finalized(self):
        self.consultation.status = 'finalized'
        self.consultation.save()

        self.auth(self.doctor)
        response = self.client.patch(
            self.finalize_url(self.consultation.id),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_finalize_without_diagnosis(self):
        self.consultation.diagnosis = '   '
        self.consultation.save()

        self.auth(self.doctor)
        response = self.client.patch(
            self.finalize_url(self.consultation.id),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receptionist_cannot_finalize(self):
        self.auth(self.receptionist)
        response = self.client.patch(
            self.finalize_url(self.consultation.id),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_finalize_nonexistent_returns_404(self):
        self.auth(self.doctor)
        response = self.client.patch(self.finalize_url(99999), format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ==========================================================================
# DELETE
# ==========================================================================

class TestConsultationDelete(ConsultationTestBase):

    def test_assigned_doctor_can_soft_delete_draft(self):
        self.auth(self.doctor)
        response = self.client.delete(
            self.consultation_url(self.consultation.id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Confirm it is no longer retrievable
        self.auth(self.doctor)
        get_response = self.client.get(
            self.consultation_url(self.consultation.id)
        )
        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_delete_any_draft(self):
        self.auth(self.admin)
        response = self.client.delete(
            self.consultation_url(self.consultation.id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_doctor_cannot_delete(self):
        self.auth(self.other_doctor)
        response = self.client.delete(
            self.consultation_url(self.consultation.id)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_delete_finalized_consultation(self):
        self.consultation.status = 'finalized'
        self.consultation.save()

        self.auth(self.doctor)
        response = self.client.delete(
            self.consultation_url(self.consultation.id)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receptionist_cannot_delete(self):
        self.auth(self.receptionist)
        response = self.client.delete(
            self.consultation_url(self.consultation.id)
        )
        # Receptionist passes the permission check (IsAdminDoctorOrReceptionist)
        # but is blocked by the service layer, which returns 400.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_nonexistent_returns_400(self):
        self.auth(self.doctor)
        response = self.client.delete(self.consultation_url(99999))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)