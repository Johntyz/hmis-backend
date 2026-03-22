"""
Service layer tests for ConsultationService.

These tests call the service methods directly — no HTTP, no serializers.
They verify that all business rules raise the correct ValueError
with a meaningful message.

Test groups:
    TestCreateConsultation      → creation rules
    TestUpdateConsultation      → update rules
    TestFinalizeConsultation    → finalization rules
    TestSoftDeleteConsultation  → soft delete rules
    TestListAndGet              → query methods
"""

from apps.consultations.services import ConsultationService
from apps.consultations.models import Consultation
from .base import ConsultationTestBase


# ==========================================================================
# CREATE
# ==========================================================================

class TestCreateConsultation(ConsultationTestBase):

    def test_assigned_doctor_can_create_consultation(self):
        """Happy path — assigned doctor creates a consultation."""
        # We need a fresh appointment with no consultation yet
        new_appointment = self._make_appointment(
            doctor=self.doctor,
            patient=self.patient,
            status='in_progress',
        )
        data = {
            'appointment': new_appointment,
            'diagnosis': 'Malaria suspected.',
        }
        consultation = ConsultationService.create_consultation(data, self.doctor)

        self.assertIsNotNone(consultation.pk)
        self.assertEqual(consultation.doctor, self.doctor)
        self.assertEqual(consultation.status, 'draft')
        self.assertEqual(consultation.created_by, self.doctor)

    def test_other_doctor_cannot_create_consultation(self):
        """A doctor who is NOT assigned to the appointment is blocked."""
        new_appointment = self._make_appointment(
            doctor=self.doctor,
            patient=self.patient,
            status='in_progress',
        )
        data = {
            'appointment': new_appointment,
            'diagnosis': 'Some diagnosis.',
        }
        with self.assertRaises(ValueError) as ctx:
            ConsultationService.create_consultation(data, self.other_doctor)

        self.assertIn('own appointments', str(ctx.exception))

    def test_cannot_create_for_scheduled_appointment(self):
        """Appointment must be in_progress or completed — not scheduled."""
        scheduled_appt = self._make_appointment(
            doctor=self.doctor,
            patient=self.patient,
            status='scheduled',
        )
        data = {
            'appointment': scheduled_appt,
            'diagnosis': 'Too early.',
        }
        with self.assertRaises(ValueError) as ctx:
            ConsultationService.create_consultation(data, self.doctor)

        self.assertIn('in_progress or completed', str(ctx.exception))

    def test_cannot_create_duplicate_consultation(self):
        """An appointment that already has a consultation cannot get another."""
        # self.appointment already has self.consultation from setUp
        data = {
            'appointment': self.appointment,
            'diagnosis': 'Duplicate attempt.',
        }
        with self.assertRaises(ValueError) as ctx:
            ConsultationService.create_consultation(data, self.doctor)

        self.assertIn('already has a consultation', str(ctx.exception))

    def test_doctor_field_is_set_from_appointment_not_request(self):
        """The doctor on the consultation comes from the appointment, not manually passed."""
        new_appointment = self._make_appointment(
            doctor=self.doctor,
            patient=self.patient,
            status='in_progress',
        )
        data = {'appointment': new_appointment, 'diagnosis': 'Test.'}
        consultation = ConsultationService.create_consultation(data, self.doctor)

        self.assertEqual(consultation.doctor, self.doctor)


# ==========================================================================
# UPDATE
# ==========================================================================

class TestUpdateConsultation(ConsultationTestBase):

    def test_assigned_doctor_can_update_draft(self):
        """Assigned doctor can update a draft consultation."""
        updated = ConsultationService.update_consultation(
            self.consultation.id,
            {'diagnosis': 'Updated diagnosis.'},
            self.doctor,
        )
        self.assertEqual(updated.diagnosis, 'Updated diagnosis.')
        self.assertEqual(updated.updated_by, self.doctor)

    def test_other_doctor_cannot_update(self):
        """A different doctor cannot update someone else's consultation."""
        with self.assertRaises(ValueError) as ctx:
            ConsultationService.update_consultation(
                self.consultation.id,
                {'diagnosis': 'Unauthorized edit.'},
                self.other_doctor,
            )
        self.assertIn('own consultations', str(ctx.exception))

    def test_cannot_update_finalized_consultation(self):
        """Finalized consultations are locked — no updates allowed."""
        self.consultation.status = 'finalized'
        self.consultation.save()

        with self.assertRaises(ValueError) as ctx:
            ConsultationService.update_consultation(
                self.consultation.id,
                {'diagnosis': 'Trying to edit a locked record.'},
                self.doctor,
            )
        self.assertIn('finalized', str(ctx.exception))

    def test_update_nonexistent_consultation_raises_error(self):
        """Updating a consultation ID that does not exist raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            ConsultationService.update_consultation(
                99999,
                {'diagnosis': 'Ghost record.'},
                self.doctor,
            )
        self.assertIn('not found', str(ctx.exception).lower())


# ==========================================================================
# FINALIZE
# ==========================================================================

class TestFinalizeConsultation(ConsultationTestBase):

    def test_assigned_doctor_can_finalize(self):
        """Happy path — assigned doctor finalizes a draft consultation."""
        finalized = ConsultationService.finalize_consultation(
            self.consultation.id,
            self.doctor,
        )
        self.assertEqual(finalized.status, 'finalized')
        self.assertEqual(finalized.updated_by, self.doctor)

    def test_other_doctor_cannot_finalize(self):
        """A different doctor cannot finalize someone else's consultation."""
        with self.assertRaises(ValueError) as ctx:
            ConsultationService.finalize_consultation(
                self.consultation.id,
                self.other_doctor,
            )
        self.assertIn('own consultations', str(ctx.exception))

    def test_cannot_finalize_already_finalized(self):
        """Cannot finalize a consultation that is already finalized."""
        self.consultation.status = 'finalized'
        self.consultation.save()

        with self.assertRaises(ValueError) as ctx:
            ConsultationService.finalize_consultation(
                self.consultation.id,
                self.doctor,
            )
        self.assertIn('finalized', str(ctx.exception))

    def test_cannot_finalize_without_diagnosis(self):
        """A blank or whitespace-only diagnosis blocks finalization."""
        self.consultation.diagnosis = '   '
        self.consultation.save()

        with self.assertRaises(ValueError) as ctx:
            ConsultationService.finalize_consultation(
                self.consultation.id,
                self.doctor,
            )
        self.assertIn('diagnosis', str(ctx.exception))

    def test_finalize_nonexistent_consultation_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            ConsultationService.finalize_consultation(99999, self.doctor)
        self.assertIn('not found', str(ctx.exception).lower())


# ==========================================================================
# SOFT DELETE
# ==========================================================================

class TestSoftDeleteConsultation(ConsultationTestBase):

    def test_assigned_doctor_can_soft_delete_draft(self):
        """Assigned doctor can soft delete their own draft consultation."""
        ConsultationService.soft_delete_consultation(
            self.consultation.id,
            self.doctor,
        )
        self.consultation.refresh_from_db()
        self.assertIsNotNone(self.consultation.deleted_at)

    def test_admin_can_soft_delete_any_draft(self):
        """Admin can soft delete any draft consultation."""
        ConsultationService.soft_delete_consultation(
            self.consultation.id,
            self.admin,
        )
        self.consultation.refresh_from_db()
        self.assertIsNotNone(self.consultation.deleted_at)

    def test_other_doctor_cannot_delete(self):
        """A doctor cannot delete another doctor's consultation."""
        with self.assertRaises(ValueError) as ctx:
            ConsultationService.soft_delete_consultation(
                self.consultation.id,
                self.other_doctor,
            )
        self.assertIn('own consultations', str(ctx.exception))

    def test_cannot_delete_finalized_consultation(self):
        """Finalized consultations cannot be deleted by anyone."""
        self.consultation.status = 'finalized'
        self.consultation.save()

        with self.assertRaises(ValueError) as ctx:
            ConsultationService.soft_delete_consultation(
                self.consultation.id,
                self.doctor,
            )
        self.assertIn('finalized', str(ctx.exception))

    def test_delete_nonexistent_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            ConsultationService.soft_delete_consultation(99999, self.doctor)
        self.assertIn('not found', str(ctx.exception).lower())


# ==========================================================================
# LIST & GET
# ==========================================================================

class TestListAndGetConsultation(ConsultationTestBase):

    def test_doctor_only_sees_own_consultations(self):
        """list_consultations filters by doctor when role is 'doctor'."""
        # Create a consultation for other_doctor
        other_appointment = self._make_appointment(
            doctor=self.other_doctor,
            patient=self.patient,
            status='in_progress',
        )
        self._make_consultation(
            appointment=other_appointment,
            doctor=self.other_doctor,
        )

        results = ConsultationService.list_consultations(self.doctor)
        doctor_ids = set(results.values_list('doctor_id', flat=True))

        self.assertEqual(doctor_ids, {self.doctor.id})

    def test_admin_sees_all_consultations(self):
        """Admins get the full unfiltered queryset."""
        other_appointment = self._make_appointment(
            doctor=self.other_doctor,
            patient=self.patient,
            status='in_progress',
        )
        self._make_consultation(
            appointment=other_appointment,
            doctor=self.other_doctor,
        )

        results = ConsultationService.list_consultations(self.admin)
        self.assertGreaterEqual(results.count(), 2)

    def test_get_consultation_by_id_returns_correct_record(self):
        result = ConsultationService.get_consultation_by_id(self.consultation.id)
        self.assertEqual(result.id, self.consultation.id)

    def test_get_consultation_returns_none_for_soft_deleted(self):
        """Soft deleted consultations should not be returned."""
        from django.utils import timezone
        self.consultation.deleted_at = timezone.now()
        self.consultation.save()

        result = ConsultationService.get_consultation_by_id(self.consultation.id)
        self.assertIsNone(result)

    def test_get_nonexistent_consultation_returns_none(self):
        result = ConsultationService.get_consultation_by_id(99999)
        self.assertIsNone(result)