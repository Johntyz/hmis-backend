from django.db import models
from apps.appointments.models import Appointment
from apps.users.models import CustomUser


class Consultation(models.Model):
    """
    Represents the clinical record of a consultation
    that occurs during an appointment.

    A consultation can only be created by the assigned doctor
    once the appointment is in_progress or completed.

    Status lifecycle:
        draft       -> Doctor is still filling in details
        finalized   -> Doctor has locked the record
                       No further edits allowed after this point

    Audit trail:
        created_by  -> Doctor who created the consultation
        updated_by  -> Last staff member who modified it
    """

    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('finalized', 'Finalized'),
    )

    VALID_TRANSITIONS = {
        'draft':     ['finalized'],
        'finalized': [],            # Terminal state — no further changes allowed
    }

    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.PROTECT,       # Never lose consultation if appointment is deleted
        related_name='consultation'
    )

    # Direct doctor link for simpler ownership checks and queries
    doctor = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='consultations',
    )

    diagnosis = models.TextField()

    notes = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    # Audit trail — who created and last modified this record
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='consultations_created',
        null=True,
        blank=True
    )

    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='consultations_updated',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (
            f"Consultation — Dr. {self.doctor.get_full_name()} | "
            f"Patient: {self.appointment.patient} | "
            f"Status: {self.get_status_display()}"
        )