"""
Service layer tests for PrescriptionService.

Tests call service methods directly — no HTTP involved.
Verifies all business rules raise the correct ValueError.

Test groups:
    TestCreatePrescription      → creation rules
    TestUpdatePrescription      → update rules
    TestUpdatePrescriptionStatus → status transition rules
    TestSoftDeletePrescription  → soft delete rules
    TestListAndGetPrescription  → query methods
"""

from django.utils import timezone
from apps.prescriptions.services import PrescriptionService
from apps.prescriptions.models import Prescription
from .base import PrescriptionTestBase


# ==========================================================================
# CREATE
# ==========================================================================

class TestCreatePrescription(PrescriptionTestBase):

    def _fresh_consultation(self, doctor=None):
        """Returns a draft consultation with no prescriptions."""
        appt = self._make_appointment(doctor or self.doctor, self.patient)
        return self._make_consultation(appt, doctor or self.doctor)

    def test_assigned_doctor_can_create_prescription(self):
        """Happy path — doctor prescribes for their own draft consultation."""
        consultation = self._fresh_consultation()
        data = {
            'consultation': consultation,
            'medication_name': 'Paracetamol',
            'dosage': '1000mg',
            'frequency': 'Three times daily',
            'duration': '3 days',
        }
        prescription = PrescriptionService.create_prescription(data, self.doctor)

        self.assertIsNotNone(prescription.pk)
        self.assertEqual(prescription.status, 'active')
        self.assertEqual(prescription.patient, self.patient)
        self.assertEqual(prescription.created_by, self.doctor)

    def test_patient_is_derived_from_consultation_not_passed_in(self):
        """Patient FK is set automatically — never trusted from the caller."""
        consultation = self._fresh_consultation()
        data = {
            'consultation': consultation,
            'medication_name': 'Ibuprofen',
            'dosage': '400mg',
            'frequency': 'Twice daily',
            'duration': '5 days',
        }
        prescription = PrescriptionService.create_prescription(data, self.doctor)
        self.assertEqual(prescription.patient, consultation.appointment.patient)

    def test_other_doctor_cannot_prescribe_for_unowned_consultation(self):
        """A doctor cannot prescribe for another doctor's consultation."""
        consultation = self._fresh_consultation(doctor=self.doctor)
        data = {
            'consultation': consultation,
            'medication_name': 'Metformin',
            'dosage': '500mg',
            'frequency': 'Once daily',
            'duration': '30 days',
        }
        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.create_prescription(data, self.other_doctor)

        self.assertIn('own consultations', str(ctx.exception))

    def test_cannot_prescribe_for_finalized_consultation(self):
        """Prescriptions cannot be added once a consultation is finalized."""
        consultation = self._fresh_consultation()
        consultation.status = 'finalized'
        consultation.save()

        data = {
            'consultation': consultation,
            'medication_name': 'Aspirin',
            'dosage': '100mg',
            'frequency': 'Once daily',
            'duration': '14 days',
        }
        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.create_prescription(data, self.doctor)

        self.assertIn('draft', str(ctx.exception))

    def test_multiple_prescriptions_allowed_per_consultation(self):
        """A consultation can have more than one prescription."""
        consultation = self._fresh_consultation()
        for name in ['Drug A', 'Drug B', 'Drug C']:
            PrescriptionService.create_prescription({
                'consultation': consultation,
                'medication_name': name,
                'dosage': '100mg',
                'frequency': 'Once daily',
                'duration': '5 days',
            }, self.doctor)

        count = Prescription.objects.filter(
            consultation=consultation,
            deleted_at__isnull=True
        ).count()
        self.assertEqual(count, 3)


# ==========================================================================
# UPDATE
# ==========================================================================

class TestUpdatePrescription(PrescriptionTestBase):

    def test_assigned_doctor_can_update_active_prescription(self):
        """Doctor can update dosage on an active prescription."""
        updated = PrescriptionService.update_prescription(
            self.prescription.id,
            {'dosage': '250mg'},
            self.doctor,
        )
        self.assertEqual(updated.dosage, '250mg')
        self.assertEqual(updated.updated_by, self.doctor)

    def test_other_doctor_cannot_update(self):
        """A doctor cannot edit another doctor's prescription."""
        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.update_prescription(
                self.prescription.id,
                {'dosage': '250mg'},
                self.other_doctor,
            )
        self.assertIn('own consultations', str(ctx.exception))

    def test_cannot_update_completed_prescription(self):
        """Completed prescriptions are terminal — no updates allowed."""
        self.prescription.status = 'completed'
        self.prescription.save()

        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.update_prescription(
                self.prescription.id,
                {'dosage': '250mg'},
                self.doctor,
            )
        self.assertIn('completed', str(ctx.exception))

    def test_cannot_update_cancelled_prescription(self):
        """Cancelled prescriptions are terminal — no updates allowed."""
        self.prescription.status = 'cancelled'
        self.prescription.save()

        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.update_prescription(
                self.prescription.id,
                {'dosage': '250mg'},
                self.doctor,
            )
        self.assertIn('cancelled', str(ctx.exception))

    def test_cannot_update_prescription_on_finalized_consultation(self):
        """Once a consultation is finalized, its prescriptions are locked."""
        self.consultation.status = 'finalized'
        self.consultation.save()

        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.update_prescription(
                self.prescription.id,
                {'dosage': '250mg'},
                self.doctor,
            )
        self.assertIn('finalized', str(ctx.exception))

    def test_consultation_fk_cannot_be_changed_on_update(self):
        """Consultation FK is stripped from update data — cannot be reassigned."""
        other_appt = self._make_appointment(self.doctor, self.patient)
        other_consultation = self._make_consultation(other_appt, self.doctor)

        updated = PrescriptionService.update_prescription(
            self.prescription.id,
            {'consultation': other_consultation, 'dosage': '250mg'},
            self.doctor,
        )
        # consultation must remain the original one
        self.assertEqual(updated.consultation, self.consultation)
        self.assertEqual(updated.dosage, '250mg')

    def test_update_nonexistent_prescription_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.update_prescription(99999, {'dosage': '10mg'}, self.doctor)
        self.assertIn('not found', str(ctx.exception).lower())


# ==========================================================================
# STATUS TRANSITIONS
# ==========================================================================

class TestUpdatePrescriptionStatus(PrescriptionTestBase):

    def test_doctor_can_mark_active_as_completed(self):
        updated = PrescriptionService.update_status(
            self.prescription.id, 'completed', self.doctor
        )
        self.assertEqual(updated.status, 'completed')

    def test_doctor_can_mark_active_as_cancelled(self):
        updated = PrescriptionService.update_status(
            self.prescription.id, 'cancelled', self.doctor
        )
        self.assertEqual(updated.status, 'cancelled')

    def test_admin_can_update_status(self):
        """Admins can change status on any prescription."""
        updated = PrescriptionService.update_status(
            self.prescription.id, 'completed', self.admin
        )
        self.assertEqual(updated.status, 'completed')

    def test_other_doctor_cannot_change_status(self):
        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.update_status(
                self.prescription.id, 'completed', self.other_doctor
            )
        self.assertIn('own prescriptions', str(ctx.exception))

    def test_cannot_transition_from_completed(self):
        """Completed is a terminal state — no further transitions."""
        self.prescription.status = 'completed'
        self.prescription.save()

        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.update_status(
                self.prescription.id, 'cancelled', self.doctor
            )
        self.assertIn("Cannot transition", str(ctx.exception))

    def test_cannot_transition_from_cancelled(self):
        """Cancelled is a terminal state — no further transitions."""
        self.prescription.status = 'cancelled'
        self.prescription.save()

        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.update_status(
                self.prescription.id, 'active', self.doctor
            )
        self.assertIn("Cannot transition", str(ctx.exception))

    def test_cannot_transition_to_invalid_status(self):
        """Active cannot jump to an unknown status."""
        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.update_status(
                self.prescription.id, 'suspended', self.doctor
            )
        self.assertIn("Cannot transition", str(ctx.exception))

    def test_status_update_nonexistent_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.update_status(99999, 'completed', self.doctor)
        self.assertIn('not found', str(ctx.exception).lower())


# ==========================================================================
# SOFT DELETE
# ==========================================================================

class TestSoftDeletePrescription(PrescriptionTestBase):

    def test_assigned_doctor_can_soft_delete_active_prescription(self):
        PrescriptionService.soft_delete_prescription(
            self.prescription.id, self.doctor
        )
        self.prescription.refresh_from_db()
        self.assertIsNotNone(self.prescription.deleted_at)

    def test_admin_can_soft_delete_any_active_prescription(self):
        PrescriptionService.soft_delete_prescription(
            self.prescription.id, self.admin
        )
        self.prescription.refresh_from_db()
        self.assertIsNotNone(self.prescription.deleted_at)

    def test_cancelled_prescription_can_be_deleted(self):
        """Cancelled is not in the blocked list — deletion is allowed."""
        self.prescription.status = 'cancelled'
        self.prescription.save()

        PrescriptionService.soft_delete_prescription(
            self.prescription.id, self.doctor
        )
        self.prescription.refresh_from_db()
        self.assertIsNotNone(self.prescription.deleted_at)

    def test_completed_prescription_cannot_be_deleted(self):
        """Completed prescriptions are permanently locked."""
        self.prescription.status = 'completed'
        self.prescription.save()

        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.soft_delete_prescription(
                self.prescription.id, self.doctor
            )
        self.assertIn('completed', str(ctx.exception))

    def test_cannot_delete_prescription_on_finalized_consultation(self):
        self.consultation.status = 'finalized'
        self.consultation.save()

        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.soft_delete_prescription(
                self.prescription.id, self.doctor
            )
        self.assertIn('finalized', str(ctx.exception))

    def test_other_doctor_cannot_delete(self):
        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.soft_delete_prescription(
                self.prescription.id, self.other_doctor
            )
        self.assertIn('own prescriptions', str(ctx.exception))

    def test_delete_nonexistent_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            PrescriptionService.soft_delete_prescription(99999, self.doctor)
        self.assertIn('not found', str(ctx.exception).lower())


# ==========================================================================
# LIST & GET
# ==========================================================================

class TestListAndGetPrescription(PrescriptionTestBase):

    def test_doctor_only_sees_own_prescriptions(self):
        """Doctors are scoped to prescriptions from their own consultations."""
        other_appt = self._make_appointment(self.other_doctor, self.patient)
        other_consultation = self._make_consultation(other_appt, self.other_doctor)
        self._make_prescription(other_consultation, self.other_doctor, medication_name='Drug B')

        results = PrescriptionService.list_prescriptions(self.doctor)
        for p in results:
            self.assertEqual(p.consultation.appointment.doctor, self.doctor)

    def test_admin_sees_all_prescriptions(self):
        other_appt = self._make_appointment(self.other_doctor, self.patient)
        other_consultation = self._make_consultation(other_appt, self.other_doctor)
        self._make_prescription(other_consultation, self.other_doctor, medication_name='Drug B')

        results = PrescriptionService.list_prescriptions(self.admin)
        self.assertGreaterEqual(results.count(), 2)

    def test_filter_by_patient_id(self):
        """patient_id filter narrows results to a specific patient."""
        results = PrescriptionService.list_prescriptions(
            self.admin, patient_id=self.patient.id
        )
        for p in results:
            self.assertEqual(p.patient_id, self.patient.id)

    def test_get_prescription_by_id_returns_correct_record(self):
        result = PrescriptionService.get_prescription_by_id(self.prescription.id)
        self.assertEqual(result.id, self.prescription.id)

    def test_get_returns_none_for_soft_deleted(self):
        self.prescription.deleted_at = timezone.now()
        self.prescription.save()

        result = PrescriptionService.get_prescription_by_id(self.prescription.id)
        self.assertIsNone(result)

    def test_get_nonexistent_returns_none(self):
        result = PrescriptionService.get_prescription_by_id(99999)
        self.assertIsNone(result)