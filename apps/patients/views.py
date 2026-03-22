from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .serializers import PatientReadSerializer, PatientWriteSerializer
from .services import PatientService
from apps.users.permissions import IsAdmin, IsAdminDoctorOrReceptionist


class PatientViewSet(viewsets.ViewSet):
    """
    ViewSet for managing patient records.

    Permissions by action:
    - list, retrieve, search  → any authenticated staff (admin, doctor, receptionist)
    - create, update          → admin and receptionist only (doctors don't register patients)
    - destroy                 → admin only

    Business logic is fully delegated to PatientService.
    """

    def get_permissions(self):
        """
        Assign permissions based on the action being performed.
        """
        if self.action == 'destroy':
            return [IsAdmin()]
        if self.action in ['create', 'partial_update']:
            return [IsAdminDoctorOrReceptionist()]
        # list, retrieve, search — any authenticated staff
        return [IsAuthenticated()]

    def list(self, request):
        """
        GET /patients/
        Returns all active patients, ordered by last name.
        Supports optional search via ?q= query parameter.
        """
        query = request.query_params.get('q', '').strip()

        if query:
            patients = PatientService.search_patients(query)
        else:
            patients = PatientService.list_patients()

        serializer = PatientReadSerializer(patients, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        GET /patients/{id}/
        Returns a single patient record.
        """
        patient = PatientService.get_patient_by_id(pk)
        if not patient:
            raise NotFound("Patient not found.")

        serializer = PatientReadSerializer(patient)
        return Response(serializer.data)

    def create(self, request):
        """
        POST /patients/
        Registers a new patient.
        Only admins and receptionists can register patients.
        """
        serializer = PatientWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            patient = PatientService.create_patient(serializer.validated_data)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(
            PatientReadSerializer(patient).data,
            status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, pk=None):
        """
        PATCH /patients/{id}/
        Updates a patient's details.
        Only admins and receptionists can update patient records.
        """
        patient = PatientService.get_patient_by_id(pk)
        if not patient:
            raise NotFound("Patient not found.")

        serializer = PatientWriteSerializer(
            patient,
            data=request.data,
            partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated_patient = PatientService.update_patient(pk, serializer.validated_data)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(PatientReadSerializer(updated_patient).data)

    def destroy(self, request, pk=None):
        """
        DELETE /patients/{id}/
        Soft deletes a patient record.
        Only admins can delete patients.
        """
        try:
            PatientService.soft_delete_patient(pk)
        except ValueError as e:
            raise NotFound({'detail': str(e)})

        return Response(
            {'detail': 'Patient record deactivated successfully.'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'], url_path='deleted')
    def deleted(self, request):
        """
        GET /patients/deleted/
        Returns all soft-deleted patients.
        Admin only.
        """
        if not request.user.is_superuser:
            return Response(
                {'detail': 'Admin access required.'},
                status=status.HTTP_403_FORBIDDEN
            )
        patients = PatientService.list_deleted_patients()
        return Response(PatientReadSerializer(patients, many=True).data)

    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        """
        POST /patients/{id}/reactivate/
        Reactivates a soft-deleted patient.
        Admin only.
        """
        if not request.user.is_superuser:
            return Response(
                {'detail': 'Admin access required.'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            patient = PatientService.reactivate_patient(pk)
        except ValueError as e:
            raise NotFound({'detail': str(e)})

        return Response(PatientReadSerializer(patient).data)