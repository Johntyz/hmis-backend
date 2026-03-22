"""
Base test case for Prescription module tests.

Extends the fixture chain from the Consultation module:
    CustomUser → Patient → Appointment → Consultation → Prescription

All test classes inherit from PrescriptionTestBase which provides:
- Four users: doctor, other_doctor, receptionist, admin
- One patient
- One appointment (in_progress, assigned to self.doctor)
- One consultation (draft, assigned to self.doctor)
- One prescription (active, linked to self.consultation)
- JWT auth helper: self.auth(user)
"""

from django.utils import timezone
from rest_framework.test import APITestCase, APIClient

from apps.users.models import CustomUser
from apps.patients.models import Patient
from apps.appointments.models import Appointment
from apps.consultations.models import Consultation
from apps.prescriptions.models import Prescription


class PrescriptionTestBase(APITestCase):

    PASSWORD = 'StrongPass123!'
    TOKEN_URL = '/api/users/auth/login/'
    PRESCRIPTIONS_URL = '/api/prescriptions/'

    def prescription_url(self, pk):
        return f'{self.PRESCRIPTIONS_URL}{pk}/'

    def status_url(self, pk):
        return f'{self.PRESCRIPTIONS_URL}{pk}/status/'

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
        self.appointment = self._make_appointment(self.doctor, self.patient)
        self.consultation = self._make_consultation(self.appointment, self.doctor)
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

    def _make_patient(self):
        return Patient.objects.create(
            first_name='John',
            last_name='Doe',
            date_of_birth='1990-01-15',
            gender='M',
            phone_number='0700000001',
            email='john.doe@hmis.test',
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

    def _make_consultation(self, appointment, doctor, status='draft',
                           diagnosis='Patient presents with fever.'):
        return Consultation.objects.create(
            appointment=appointment,
            doctor=doctor,
            diagnosis=diagnosis,
            status=status,
            created_by=doctor,
            updated_by=doctor,
        )

    def _make_prescription(self, consultation, doctor, status='active',
                           medication_name='Amoxicillin'):
        return Prescription.objects.create(
            consultation=consultation,
            patient=consultation.appointment.patient,
            medication_name=medication_name,
            dosage='500mg',
            frequency='Twice daily',
            duration='7 days',
            instructions='Take after meals.',
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
        self.assertIsNotNone(token, "No 'access' key in login response.")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def clear_auth(self):
        self.client.credentials()