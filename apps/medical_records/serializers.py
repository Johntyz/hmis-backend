from rest_framework import serializers
from apps.patients.models import Patient
from apps.consultations.models import Consultation
from apps.prescriptions.models import Prescription


# ─────────────────────────────────────────────
# SHARED PATIENT SUMMARY
# ─────────────────────────────────────────────

class MedicalRecordPatientSerializer(serializers.ModelSerializer):
    """
    Patient summary used in all medical record responses.
    Safe for all roles — no clinical data here.
    """
    full_name = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',
            'first_name',
            'last_name',
            'date_of_birth',
            'age',
            'gender',
            'national_id',
            'phone_number',
            'email',
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_age(self, obj):
        from datetime import date
        today = date.today()
        dob = obj.date_of_birth
        return today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )


# ─────────────────────────────────────────────
# PRESCRIPTION SERIALIZERS (per role)
# ─────────────────────────────────────────────

class MedicalRecordPrescriptionFullSerializer(serializers.ModelSerializer):
    """
    Full prescription details for doctors and admins.
    """
    status_display = serializers.SerializerMethodField()
    prescribed_by = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = [
            'id',
            'medication_name',
            'dosage',
            'frequency',
            'duration',
            'instructions',
            'status',
            'status_display',
            'prescribed_by',
            'created_at',
        ]

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_prescribed_by(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None


class MedicalRecordPrescriptionRestrictedSerializer(serializers.ModelSerializer):
    """
    Restricted prescription view for receptionists.
    Only medication name and status — no clinical dosage details.
    """
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = [
            'id',
            'medication_name',
            'status',
            'status_display',
        ]

    def get_status_display(self, obj):
        return obj.get_status_display()


# ─────────────────────────────────────────────
# CONSULTATION SERIALIZERS (per role)
# ─────────────────────────────────────────────

class MedicalRecordConsultationFullSerializer(serializers.ModelSerializer):
    """
    Full consultation details for doctors and admins.
    Includes diagnosis, notes, and full prescription details.
    """
    doctor_name = serializers.SerializerMethodField()
    appointment_date = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    prescriptions = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = [
            'id',
            'doctor_name',
            'appointment_date',
            'diagnosis',
            'notes',
            'status',
            'status_display',
            'prescriptions',
            'created_at',
        ]

    def get_doctor_name(self, obj):
        return f"Dr. {obj.appointment.doctor.get_full_name()}"

    def get_appointment_date(self, obj):
        return obj.appointment.appointment_date

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_prescriptions(self, obj):
        return MedicalRecordPrescriptionFullSerializer(
            obj.prescriptions.all(),
            many=True
        ).data


class MedicalRecordConsultationRestrictedSerializer(serializers.ModelSerializer):
    """
    Restricted consultation view for receptionists.
    No diagnosis, no notes, no clinical prescription details.
    Only enough for administrative purposes.
    """
    doctor_name = serializers.SerializerMethodField()
    appointment_date = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    prescriptions = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = [
            'id',
            'doctor_name',
            'appointment_date',
            'status',
            'status_display',
            'prescriptions',
            'created_at',
        ]

    def get_doctor_name(self, obj):
        return f"Dr. {obj.appointment.doctor.get_full_name()}"

    def get_appointment_date(self, obj):
        return obj.appointment.appointment_date

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_prescriptions(self, obj):
        return MedicalRecordPrescriptionRestrictedSerializer(
            obj.prescriptions.all(),
            many=True
        ).data


# ─────────────────────────────────────────────
# TOP-LEVEL MEDICAL RECORD SERIALIZERS
# ─────────────────────────────────────────────

class MedicalRecordFullSerializer(serializers.Serializer):
    """
    Full medical record for doctors and admins.
    Includes complete clinical data.
    """
    patient = MedicalRecordPatientSerializer()
    consultations = serializers.SerializerMethodField()
    total_consultations = serializers.SerializerMethodField()

    def get_consultations(self, obj):
        return MedicalRecordConsultationFullSerializer(
            obj['consultations'],
            many=True
        ).data

    def get_total_consultations(self, obj):
        return obj['consultations'].count()


class MedicalRecordRestrictedSerializer(serializers.Serializer):
    """
    Restricted medical record for receptionists.
    No clinical data — diagnosis, notes, dosage details are hidden.
    """
    patient = MedicalRecordPatientSerializer()
    consultations = serializers.SerializerMethodField()
    total_consultations = serializers.SerializerMethodField()

    def get_consultations(self, obj):
        return MedicalRecordConsultationRestrictedSerializer(
            obj['consultations'],
            many=True
        ).data

    def get_total_consultations(self, obj):
        return obj['consultations'].count()


# ─────────────────────────────────────────────
# PRESCRIPTION HISTORY SERIALIZERS
# ─────────────────────────────────────────────

class PrescriptionHistoryFullSerializer(serializers.Serializer):
    """
    Full prescription history for doctors and admins.
    """
    patient = MedicalRecordPatientSerializer()
    prescriptions = serializers.SerializerMethodField()
    total_prescriptions = serializers.SerializerMethodField()

    def get_prescriptions(self, obj):
        return MedicalRecordPrescriptionFullSerializer(
            obj['prescriptions'],
            many=True
        ).data

    def get_total_prescriptions(self, obj):
        return obj['prescriptions'].count()


class PrescriptionHistoryRestrictedSerializer(serializers.Serializer):
    """
    Restricted prescription history for receptionists.
    """
    patient = MedicalRecordPatientSerializer()
    prescriptions = serializers.SerializerMethodField()
    total_prescriptions = serializers.SerializerMethodField()

    def get_prescriptions(self, obj):
        return MedicalRecordPrescriptionRestrictedSerializer(
            obj['prescriptions'],
            many=True
        ).data

    def get_total_prescriptions(self, obj):
        return obj['prescriptions'].count()