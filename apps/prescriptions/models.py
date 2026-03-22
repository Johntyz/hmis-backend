from django.db import models
from apps.consultations.models import Consultation
from apps.patients.models import Patient
from apps.users.models import CustomUser


class Prescription(models.Model):
    """
    Represents a single medication prescribed during a consultation.
    A consultation can have multiple prescriptions.

    Design decision:
        Patient is stored directly as a FK (denormalized) for
        efficient querying — e.g. "all active prescriptions for
        this patient" without traversing Consultation → Appointment.
        This is intentional and justified for a clinical workflow.

    Status lifecycle:
        active      -> Currently prescribed
        completed   -> Course finished
        cancelled   -> Discontinued by doctor

    Audit trail:
        created_by  -> Doctor who prescribed
        updated_by  -> Last person who modified the record
    """

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    VALID_TRANSITIONS = {
        'active':    ['completed', 'cancelled'],
        'completed': [],    # Terminal state
        'cancelled': [],    # Terminal state
    }

    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.PROTECT,       # Never silently lose prescription history
        related_name='prescriptions'
    )

    # Denormalized for direct patient-level queries
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name='prescriptions',null=True,blank=True
    )

    medication_name = models.CharField(max_length=255)

    dosage = models.CharField(max_length=100)
    # Example: "500mg"

    frequency = models.CharField(max_length=100)
    # Example: "Twice daily"

    duration = models.CharField(max_length=100)
    # Example: "5 days"

    instructions = models.TextField(blank=True, null=True)
    # Example: "Take after meals"

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )

    # Audit trail
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='prescriptions_created',
        null=True,
        blank=True
    )

    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='prescriptions_updated',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (
            f"{self.medication_name} {self.dosage} — "
            f"Patient: {self.patient} | "
            f"Status: {self.get_status_display()}"
        )