from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Represents a staff member in the clinic.

    Patients are NOT users — they are registered separately
    by receptionists and stored in the Patient model.

    Roles:
        - admin:        Created via Django's createsuperuser command only.
                        Manages staff accounts. Always is_superuser=True.
        - doctor:       Created by admin. Handles appointments and medical records.
        - receptionist: Created by admin. Registers patients, manages appointments.

    Admin role is included in ROLE_CHOICES so the role field is always
    populated and role-based checks are consistent across the codebase.
    Superuser status (is_superuser=True) remains the authoritative gate
    for admin permissions — role='admin' is the display label.

    Soft delete is used to deactivate staff accounts without permanently
    removing audit trail data.
    """

    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('receptionist', 'Receptionist'),
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='receptionist',
    )

    phone_number = models.CharField(
        max_length=15,
        unique=True,
        blank=True,
        null=True,
    )

    # Soft delete — deactivate staff without losing audit data
    deleted_at = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'role']

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    @property
    def is_admin(self):
        return self.is_superuser

    @property
    def is_doctor(self):
        return self.role == 'doctor'

    @property
    def is_receptionist(self):
        return self.role == 'receptionist'