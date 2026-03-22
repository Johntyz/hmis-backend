from django.shortcuts import render

import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .services import MedicalRecordService
from .serializers import (
    MedicalRecordFullSerializer,
    MedicalRecordRestrictedSerializer,
    PrescriptionHistoryFullSerializer,
    PrescriptionHistoryRestrictedSerializer,
)

logger = logging.getLogger(__name__)


class PatientMedicalRecordView(APIView):
    """
    GET /patients/{patient_id}/medical-records/

    Returns a patient's full medical history including
    all consultations and prescriptions.

    Access rules:
    - Doctors: only patients they have had appointments with.
               Only finalized consultations are shown.
    - Receptionists: all patients, but no clinical data
                     (no diagnosis, notes, or dosage details)
    - Admins: full access to everything

    This is a read-only endpoint. No data is written here.
    """

    permission_classes = [IsAuthenticated]

    def _get_serializer_class(self, requesting_user):
        """
        Returns the correct serializer based on the requesting
        user's role. Enforces data privacy automatically.
        """
        if requesting_user.is_superuser or requesting_user.role == 'doctor':
            return MedicalRecordFullSerializer
        return MedicalRecordRestrictedSerializer

    def get(self, request, patient_id):
        try:
            data = MedicalRecordService.get_patient_medical_record(
                requesting_user=request.user,
                patient_id=patient_id,
            )
        except ValueError as e:
            error_message = str(e)

            # Distinguish between not found and access denied
            if "not found" in error_message.lower():
                raise NotFound(error_message)

            raise PermissionDenied(error_message)

        except Exception as e:
            # Log the real error for debugging
            # Never expose raw exceptions to the client
            logger.error(
                f"Unexpected error fetching medical record for patient "
                f"{patient_id} by user {request.user.id}: {str(e)}",
                exc_info=True
            )
            return Response(
                {'detail': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        serializer_class = self._get_serializer_class(request.user)
        serializer = serializer_class(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PatientPrescriptionHistoryView(APIView):
    """
    GET /patients/{patient_id}/prescriptions/

    Returns a quick overview of all prescriptions for a patient
    without loading the full consultation history.

    Useful for:
    - Doctors reviewing a patient's medication history
    - Receptionists checking active prescriptions for billing

    Same access rules as PatientMedicalRecordView apply.
    This is a read-only endpoint. No data is written here.
    """

    permission_classes = [IsAuthenticated]

    def _get_serializer_class(self, requesting_user):
        if requesting_user.is_superuser or requesting_user.role == 'doctor':
            return PrescriptionHistoryFullSerializer
        return PrescriptionHistoryRestrictedSerializer

    def get(self, request, patient_id):
        try:
            data = MedicalRecordService.get_patient_prescription_history(
                requesting_user=request.user,
                patient_id=patient_id,
            )
        except ValueError as e:
            error_message = str(e)

            if "not found" in error_message.lower():
                raise NotFound(error_message)

            raise PermissionDenied(error_message)

        except Exception as e:
            logger.error(
                f"Unexpected error fetching prescription history for patient "
                f"{patient_id} by user {request.user.id}: {str(e)}",
                exc_info=True
            )
            return Response(
                {'detail': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        serializer_class = self._get_serializer_class(request.user)
        serializer = serializer_class(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
