"""
Base test case for Medical Records module tests.

This module is read-only — no write endpoints exist.
The fixture chain is richer than previous modules because
the service aggregates data across Patient → Appointment
→ Consultation → Prescription.

Fixtures built in setUp():
    self.doctor         → CustomUser(role='doctor')
    self.other_doctor   → CustomUser(role='doctor')  — no link to self.patient
    self.receptionist   → CustomUser(role='receptionist')
    self.admin          → CustomUser(role='admin', is_superuser=True)

    self.patient        → Patient instance
    self.appointment    → Appointment(doctor=self.doctor, status='in_progress')
    self.consultation   → Consultation(status='finalized') — finalized so
                          doctors can see it in the medical record view
    self.prescription   → Prescription(status='active')

Key design decisions:
    - self.consultation is finalized — doctors only see finalized consultations
      in the medical record view. A draft would be invisible to them.
    - self.other_doctor has NO appointment with self.patient — used to test
      that doctors are blocked from accessing unrelated patient records.
"""

from django.utils import timezone
from rest_framework.test import APITestCase, APIClient

from apps.users.models import CustomUser
from apps.patients.models import Patient
from apps.appointments.models import Appointment
from apps.consultations.models import Consultation
from apps.prescriptions.models import Prescription


class MedicalRecordTestBase(APITestCase):

    PASSWORD = 'StrongPass123!'
    TOKEN_URL = '/api/users/auth/login/'

    def medical_record_url(self, patient_id):
        return f'/api/v1/patients/{patient_id}/medical-records/'

    def prescription_history_url(self, patient_id):
        return f'/api/v1/patients/{patient_id}/prescription-history/'

    # ------------------------------------------------------------------
    # setUp
    # ------------------------------------------------------------------

    def setUp(self):
        self.client = APIClient()

        self.doctor = self._make_user('doctor_one', 'doctor', 'James', 'Mwangi')
        self.other_doctor = self._make_user('doctor_two', 'doctor', 'Alice', 'Kamau')
        self.receptionist = self._make_user('receptionist_one', 'receptionist', 'Grace', 'Otieno')
        self.admin = self._make_user('admin_one', 'admin', 'Super', 'Admin',
                                     is_superuser=True, is_staff=True)

        self.patient = self._make_patient()

        # Appointment links self.doctor to self.patient
        self.appointment = self._make_appointment(self.doctor, self.patient)

        # Finalized so the doctor can see it via the medical record view
        self.consultation = self._make_consultation(
            self.appointment, self.doctor, status='finalized'
        )

        self.prescription = self._make_prescription(self.consultation, self.doctor)

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    def _make_user(self, username, role, first_name='', last_name='',
                   is_superuser=False, is_staff=False):
        return CustomUser.objects.create_user(
            username=username,
            password=self.PASSWORD,
            role=role,
            first_name=first_name,
            last_name=last_name,
            is_superuser=is_superuser,
            is_staff=is_staff,
            email=f'{username}@hmis.test',
        )

    def _make_patient(self, first_name='John', last_name='Doe',
                      phone='0700000001', email='john.doe@hmis.test'):
        return Patient.objects.create(
            first_name=first_name,
            last_name=last_name,
            date_of_birth='1990-01-15',
            gender='M',
            phone_number=phone,
            email=email,
        )

    def _make_appointment(self, doctor, patient, status='in_progress'):
        return Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=timezone.now(),
            duration_minutes=30,
            status=status,
            created_by=doctor,
        )

    def _make_consultation(self, appointment, doctor, status='finalized',
                           diagnosis='Diagnosed with hypertension.'):
        return Consultation.objects.create(
            appointment=appointment,
            doctor=doctor,
            diagnosis=diagnosis,
            notes='Patient advised on lifestyle changes.',
            status=status,
            created_by=doctor,
            updated_by=doctor,
        )

    def _make_prescription(self, consultation, doctor, status='active',
                           medication_name='Amlodipine'):
        return Prescription.objects.create(
            consultation=consultation,
            patient=consultation.appointment.patient,
            medication_name=medication_name,
            dosage='5mg',
            frequency='Once daily',
            duration='30 days',
            instructions='Take in the morning.',
            status=status,
            created_by=doctor,
            updated_by=doctor,
        )

    # ------------------------------------------------------------------
    # Auth helper
    # ------------------------------------------------------------------

    def auth(self, user):
        response = self.client.post(
            self.TOKEN_URL,
            {'username': user.username, 'password': self.PASSWORD},
            format='json',
        )
        self.assertEqual(
            response.status_code, 200,
            msg=f"Auth failed for '{user.username}': {response.data}"
        )
        token = response.data.get('access')
        self.assertIsNotNone(token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def clear_auth(self):
        self.client.credentials()
        