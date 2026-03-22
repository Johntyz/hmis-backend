"""
Base test case for Consultation module tests.

All test classes inherit from ConsultationTestBase which handles:
- Creating the three user roles (doctor, receptionist, admin)
- Creating a Patient fixture
- Creating an Appointment fixture in a valid state
- Creating a draft Consultation fixture
- JWT authentication helper

Why a shared base?
  Business rules in the Consultation module depend on the relationship
  between users, appointments, and consultations. Building those fixtures
  once here keeps every test file clean and focused on assertions only.
"""

from django.utils import timezone
from rest_framework.test import APITestCase, APIClient

# --------------------------------------------------------------------------
# These imports will resolve correctly inside your Django project.
# Adjust paths only if your app layout differs from apps/<name>/models.py
# --------------------------------------------------------------------------
from apps.users.models import CustomUser
from apps.patients.models import Patient
from apps.appointments.models import Appointment
from apps.consultations.models import Consultation


class ConsultationTestBase(APITestCase):
    """
    Shared fixtures and helpers for all consultation tests.

    Fixtures created in setUp():
        self.doctor         → CustomUser(role='doctor')
        self.other_doctor   → CustomUser(role='doctor')  — a second doctor
        self.receptionist   → CustomUser(role='receptionist')
        self.admin          → CustomUser(role='admin', is_superuser=True)
        self.patient        → Patient instance
        self.appointment    → Appointment assigned to self.doctor, status='in_progress'
        self.consultation   → Consultation (draft) linked to self.appointment

    Auth helper:
        self.auth(user)  → sets JWT Bearer token on self.client for that user
    """

    # ------------------------------------------------------------------
    # Constants — keeps magic strings in one place
    # ------------------------------------------------------------------
    PASSWORD = 'StrongPass123!'

    TOKEN_URL = '/api/users/auth/login/'

    CONSULTATIONS_URL = '/api/consultations/'

    def consultation_url(self, pk):
        return f'{self.CONSULTATIONS_URL}{pk}/'

    def finalize_url(self, pk):
        return f'{self.CONSULTATIONS_URL}{pk}/finalize/'

    # ------------------------------------------------------------------
    # setUp — runs before every single test method
    # ------------------------------------------------------------------
    def setUp(self):
        self.client = APIClient()

        # --- Users ---
        self.doctor = self._make_user(
            username='doctor_one',
            role='doctor',
            first_name='James',
            last_name='Mwangi',
        )
        self.other_doctor = self._make_user(
            username='doctor_two',
            role='doctor',
            first_name='Alice',
            last_name='Kamau',
        )
        self.receptionist = self._make_user(
            username='receptionist_one',
            role='receptionist',
            first_name='Grace',
            last_name='Otieno',
        )
        self.admin = self._make_user(
            username='admin_one',
            role='admin',
            first_name='Super',
            last_name='Admin',
            is_superuser=True,
            is_staff=True,
        )

        # --- Patient ---
        self.patient = self._make_patient()

        # --- Appointment ---
        # status=in_progress so consultations can be created against it
        self.appointment = self._make_appointment(
            doctor=self.doctor,
            patient=self.patient,
            status='in_progress',
        )

        # --- Consultation (draft, belongs to self.doctor) ---
        self.consultation = self._make_consultation(
            appointment=self.appointment,
            doctor=self.doctor,
        )

    # ------------------------------------------------------------------
    # Factory helpers — small, reusable, each does one thing
    # ------------------------------------------------------------------

    def _make_user(self, username, role, first_name='', last_name='',
                   is_superuser=False, is_staff=False):
        user = CustomUser.objects.create_user(
            username=username,
            password=self.PASSWORD,
            role=role,
            first_name=first_name,
            last_name=last_name,
            is_superuser=is_superuser,
            is_staff=is_staff,
            email=f'{username}@hmis.test',
        )
        return user

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
            notes='Initial observations.',
            status=status,
            created_by=doctor,
            updated_by=doctor,
        )

    # ------------------------------------------------------------------
    # Auth helper
    # ------------------------------------------------------------------

    def auth(self, user):
        """
        Obtains a JWT access token for the given user and sets it
        as the Authorization header on self.client.

        Usage:
            self.auth(self.doctor)
            response = self.client.get(...)
        """
        response = self.client.post(
            self.TOKEN_URL,
            {'username': user.username, 'password': self.PASSWORD},
            format='json',
        )
        self.assertEqual(
            response.status_code, 200,
            msg=(
                f"Auth failed for user '{user.username}'. "
                f"Response: {response.data}"
            )
        )
        token = response.data.get('access')
        self.assertIsNotNone(token, "No 'access' key in login response.")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def clear_auth(self):
        """Removes Authorization header — simulates unauthenticated request."""
        self.client.credentials()