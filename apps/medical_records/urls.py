from django.urls import path
from .views import PatientMedicalRecordView, PatientPrescriptionHistoryView

urlpatterns = [
    # Full medical history — consultations + prescriptions
    path(
        'patients/<int:patient_id>/medical-records/',
        PatientMedicalRecordView.as_view(),
        name='patient-medical-record'
    ),

    # Quick prescription history — medications only
    path(
        'patients/<int:patient_id>/prescription-history/',
        PatientPrescriptionHistoryView.as_view(),
        name='patient-prescription-history'
    ),
]