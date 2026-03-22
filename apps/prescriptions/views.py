from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .serializers import (
    PrescriptionWriteSerializer,
    PrescriptionStatusSerializer,
    PrescriptionDoctorReadSerializer,
    PrescriptionAdminReadSerializer,
    PrescriptionReceptionistReadSerializer,
)
from .services import PrescriptionService
from apps.users.permissions import IsAdmin, IsAdminDoctorOrReceptionist, IsDoctor


class PrescriptionViewSet(viewsets.ViewSet):
    """
    ViewSet for managing prescriptions.

    Permissions by action:
    - list, retrieve        → any authenticated staff
                              data is role-scoped:
                              doctors see full clinical details (own only)
                              receptionists see medication name and status only
                              admins see everything including audit trail
    - create, update        → assigned doctor only
    - update_status         → assigned doctor or admin
    - destroy               → assigned doctor (own, active only) or admin

    All business logic is delegated to PrescriptionService.
    """

    def get_permissions(self):
        if self.action in ['create', 'partial_update']:
            return [IsDoctor()]
        if self.action == 'destroy':
            return [IsAdminDoctorOrReceptionist()]
        return [IsAuthenticated()]

    def _get_read_serializer(self, requesting_user):
        """
        Returns the appropriate read serializer based on role.
        Enforces data privacy — receptionists never see clinical details.
        """
        if requesting_user.is_superuser:
            return PrescriptionAdminReadSerializer
        if requesting_user.role == 'doctor':
            return PrescriptionDoctorReadSerializer
        return PrescriptionReceptionistReadSerializer

    def list(self, request):
        """
        GET /prescriptions/
        Returns prescriptions scoped to the requesting user's role.
        Supports optional filtering by ?patient= for patient-level queries.
        Supports optional filtering by ?status= and ?consultation=
        """
        patient_id = request.query_params.get('patient')
        prescriptions = PrescriptionService.list_prescriptions(
            request.user,
            patient_id=patient_id
        )

        # Optional filters
        status_filter = request.query_params.get('status')
        consultation_filter = request.query_params.get('consultation')

        if status_filter:
            prescriptions = prescriptions.filter(status=status_filter)
        if consultation_filter:
            prescriptions = prescriptions.filter(consultation_id=consultation_filter)

        serializer_class = self._get_read_serializer(request.user)
        return Response(serializer_class(prescriptions, many=True).data)

    def retrieve(self, request, pk=None):
        """
        GET /prescriptions/{id}/
        Returns a single prescription.
        Doctors can only retrieve prescriptions they created.
        """
        prescription = PrescriptionService.get_prescription_by_id(pk)
        if not prescription:
            raise NotFound("Prescription not found.")

        # Doctors can only see their own prescriptions
        if request.user.role == 'doctor':
            if prescription.consultation.appointment.doctor != request.user:
                raise PermissionDenied("You can only view your own prescriptions.")

        serializer_class = self._get_read_serializer(request.user)
        return Response(serializer_class(prescription).data)

    def create(self, request):
        """
        POST /prescriptions/
        Creates a new prescription.
        Only the assigned doctor can prescribe.
        Consultation must be in draft status.
        """
        serializer = PrescriptionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            prescription = PrescriptionService.create_prescription(
                serializer.validated_data,
                request.user
            )
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(
            PrescriptionDoctorReadSerializer(prescription).data,
            status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, pk=None):
        """
        PATCH /prescriptions/{id}/
        Updates an active prescription.
        Only the prescribing doctor can update.
        Cannot update prescriptions on finalized consultations.
        """
        prescription = PrescriptionService.get_prescription_by_id(pk)
        if not prescription:
            raise NotFound("Prescription not found.")

        serializer = PrescriptionWriteSerializer(
            prescription,
            data=request.data,
            partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated = PrescriptionService.update_prescription(
                pk,
                serializer.validated_data,
                request.user
            )
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(PrescriptionDoctorReadSerializer(updated).data)

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        """
        PATCH /prescriptions/{id}/status/
        Updates prescription status following strict transition rules.
        active → completed or cancelled only.
        Only the prescribing doctor or admin can change status.
        """
        prescription = PrescriptionService.get_prescription_by_id(pk)
        if not prescription:
            raise NotFound("Prescription not found.")

        serializer = PrescriptionStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated = PrescriptionService.update_status(
                pk,
                serializer.validated_data['status'],
                request.user
            )
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        serializer_class = self._get_read_serializer(request.user)
        return Response(serializer_class(updated).data)

    def destroy(self, request, pk=None):
        """
        DELETE /prescriptions/{id}/
        Soft deletes an active prescription.
        Cannot delete completed prescriptions or those
        belonging to finalized consultations.
        Doctors can only delete their own prescriptions.
        """
        try:
            PrescriptionService.soft_delete_prescription(pk, request.user)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(
            {'detail': 'Prescription deleted successfully.'},
            status=status.HTTP_200_OK
        )