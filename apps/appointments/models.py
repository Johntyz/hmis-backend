from django.db import models
from apps.patients.models import Patient
from apps.users.models import CustomUser


class Appointment(models.Model):
    """
    Represents a scheduled meeting between a patient and a doctor.
    """

    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    )

    # Valid status transitions — enforced at service level
    VALID_TRANSITIONS = {
        'scheduled':   ['confirmed', 'cancelled'],
        'confirmed':   ['in_progress', 'cancelled'],
        'in_progress': ['completed', 'no_show'],
        'completed':   [],
        'cancelled':   [],
        'no_show':     [],
    }

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,       # Never silently delete appointment history
        related_name="appointments"
    )

    doctor = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,       # Never silently delete appointment history
        related_name="doctor_appointments"
    )

    appointment_date = models.DateTimeField()

    # Duration in minutes — needed for overlap/buffer checks
    duration_minutes = models.PositiveIntegerField(default=30)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled'
    )

    reason = models.TextField(blank=True, null=True)

    # Only the assigned doctor should write notes
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
    CustomUser,
    on_delete=models.PROTECT,
    related_name='created_appointments',
    null=True
)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.patient} with Dr. {self.doctor.get_full_name()} on {self.appointment_date}"