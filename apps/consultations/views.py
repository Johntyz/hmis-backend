from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .serializers import (
    ConsultationWriteSerializer,
    ConsultationStatusSerializer,
    ConsultationDoctorReadSerializer,
    ConsultationAdminReadSerializer,
    ConsultationReceptionistReadSerializer,
)
from .services import ConsultationService
from apps.users.permissions import IsAdmin, IsAdminDoctorOrReceptionist, IsDoctor


class ConsultationViewSet(viewsets.ViewSet):
    """
    ViewSet for managing consultations.

    Permissions by action:
    - list, retrieve    → any authenticated staff
                          but data is role-scoped:
                          doctors see clinical data (own only)
                          receptionists see no clinical data
                          admins see everything
    - create, update    → assigned doctor only
    - finalize          → assigned doctor only
    - destroy           → assigned doctor (own, draft only) or admin

    All business logic is delegated to ConsultationService.
    """

    def get_permissions(self):
        if self.action in ['create', 'partial_update', 'finalize']:
            return [IsDoctor()]
        if self.action == 'destroy':
            return [IsAdminDoctorOrReceptionist()]
        return [IsAuthenticated()]

    def _get_read_serializer(self, requesting_user):
        """
        Returns the appropriate read serializer based on the
        requesting user's role. This enforces data privacy at
        the serializer level — receptionists never see clinical data.
        """
        if requesting_user.is_superuser:
            return ConsultationAdminReadSerializer
        if requesting_user.role == 'doctor':
            return ConsultationDoctorReadSerializer
        # Receptionist — restricted view, no clinical data
        return ConsultationReceptionistReadSerializer

    def list(self, request):
        """
        GET /consultations/
        Returns consultations scoped to the requesting user's role.
        Supports optional filtering by ?appointment= and ?status=
        """
        consultations = ConsultationService.list_consultations(request.user)

        # Optional filters
        appointment_filter = request.query_params.get('appointment')
        status_filter = request.query_params.get('status')

        if appointment_filter:
            consultations = consultations.filter(appointment_id=appointment_filter)
        if status_filter:
            consultations = consultations.filter(status=status_filter)

        serializer_class = self._get_read_serializer(request.user)
        serializer = serializer_class(consultations, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        GET /consultations/{id}/
        Returns a single consultation.
        Doctors can only retrieve their own consultations.
        """
        consultation = ConsultationService.get_consultation_by_id(pk)
        if not consultation:
            raise NotFound("Consultation not found.")

        # Doctors can only see their own consultations
        if request.user.role == 'doctor' and consultation.doctor != request.user:
            raise PermissionDenied("You can only view your own consultations.")

        serializer_class = self._get_read_serializer(request.user)
        return Response(serializer_class(consultation).data)

    def create(self, request):
        """
        POST /consultations/
        Creates a new consultation.
        Only the assigned doctor can create a consultation.
        """
        serializer = ConsultationWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            consultation = ConsultationService.create_consultation(
                serializer.validated_data,
                request.user
            )
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(
            ConsultationDoctorReadSerializer(consultation).data,
            status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, pk=None):
        """
        PATCH /consultations/{id}/
        Updates a draft consultation.
        Only the assigned doctor can update.
        Finalized consultations cannot be updated.
        """
        consultation = ConsultationService.get_consultation_by_id(pk)
        if not consultation:
            raise NotFound("Consultation not found.")

        serializer = ConsultationWriteSerializer(
            consultation,
            data=request.data,
            partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated = ConsultationService.update_consultation(
                pk,
                serializer.validated_data,
                request.user
            )
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(ConsultationDoctorReadSerializer(updated).data)

    @action(detail=True, methods=['patch'], url_path='finalize')
    def finalize(self, request, pk=None):
        """
        PATCH /consultations/{id}/finalize/
        Finalizes a consultation, locking it permanently.
        Only the assigned doctor can finalize.
        Requires a diagnosis to be present.
        """
        consultation = ConsultationService.get_consultation_by_id(pk)
        if not consultation:
            raise NotFound("Consultation not found.")

        try:
            finalized = ConsultationService.finalize_consultation(pk, request.user)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(ConsultationDoctorReadSerializer(finalized).data)

    def destroy(self, request, pk=None):
        """
        DELETE /consultations/{id}/
        Soft deletes a draft consultation.
        Finalized consultations cannot be deleted.
        Doctors can only delete their own consultations.
        Admins can delete any draft consultation.
        """
        try:
            ConsultationService.soft_delete_consultation(pk, request.user)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(
            {'detail': 'Consultation deleted successfully.'},
            status=status.HTTP_200_OK
        )