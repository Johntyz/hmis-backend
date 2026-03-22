from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .serializers import (
    AppointmentReadSerializer,
    AppointmentWriteSerializer,
    AppointmentStatusSerializer,
    AppointmentNotesSerializer,
)
from .services import AppointmentService
from apps.users.permissions import IsAdmin, IsAdminDoctorOrReceptionist


class AppointmentViewSet(viewsets.ViewSet):
    """
    ViewSet for managing appointments.

    Permissions by action:
    - list, retrieve        → any authenticated staff
    - create, update        → admin and receptionist only
    - update_status         → doctor (own appointments), admin, receptionist
    - update_notes          → assigned doctor only
    - destroy               → admin, receptionist, assigned doctor (own only)

    All business logic is delegated to AppointmentService.
    """

    def get_permissions(self):
        if self.action in ['create', 'partial_update']:
            return [IsAdminDoctorOrReceptionist()]
        return [IsAuthenticated()]

    def list(self, request):
        """
        GET /appointments/
        Returns appointments scoped to the requesting user's role.
        Doctors only see their own. Admins and receptionists see all.
        Supports optional filtering by ?status= and ?patient=
        """
        appointments = AppointmentService.list_appointments(request.user)

        # Optional filters
        status_filter = request.query_params.get('status')
        patient_filter = request.query_params.get('patient')

        if status_filter:
            appointments = appointments.filter(status=status_filter)
        if patient_filter:
            appointments = appointments.filter(patient_id=patient_filter)

        serializer = AppointmentReadSerializer(appointments, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        GET /appointments/{id}/
        Returns a single appointment.
        Doctors can only retrieve their own appointments.
        """
        appointment = AppointmentService.get_appointment_by_id(pk)
        if not appointment:
            raise NotFound("Appointment not found.")

        # Doctors can only see their own appointments
        if request.user.role == 'doctor' and appointment.doctor != request.user:
            raise PermissionDenied("You can only view your own appointments.")

        serializer = AppointmentReadSerializer(appointment)
        return Response(serializer.data)

    def create(self, request):
        """
        POST /appointments/
        Creates a new appointment.
        Only admins and receptionists can create appointments.
        """
        serializer = AppointmentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            appointment = AppointmentService.create_appointment(serializer.validated_data)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(
            AppointmentReadSerializer(appointment).data,
            status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, pk=None):
        """
        PATCH /appointments/{id}/
        Updates appointment details (date, doctor, patient, reason).
        Only admins and receptionists can update appointments.
        Cannot update completed or cancelled appointments.
        """
        appointment = AppointmentService.get_appointment_by_id(pk)
        if not appointment:
            raise NotFound("Appointment not found.")

        serializer = AppointmentWriteSerializer(
            appointment,
            data=request.data,
            partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated = AppointmentService.update_appointment(pk, serializer.validated_data)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(AppointmentReadSerializer(updated).data)

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        """
        PATCH /appointments/{id}/status/
        Updates the status of an appointment following strict transition rules.
        - Doctors can mark in_progress, completed, no_show (own appointments only)
        - Receptionists and admins can confirm or cancel
        """
        appointment = AppointmentService.get_appointment_by_id(pk)
        if not appointment:
            raise NotFound("Appointment not found.")

        serializer = AppointmentStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated = AppointmentService.update_status(
                pk,
                serializer.validated_data['status'],
                request.user
            )
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(AppointmentReadSerializer(updated).data)

    @action(detail=True, methods=['patch'], url_path='notes')
    def update_notes(self, request, pk=None):
        """
        PATCH /appointments/{id}/notes/
        Allows the assigned doctor to write consultation notes.
        Only the assigned doctor can access this endpoint.
        """
        appointment = AppointmentService.get_appointment_by_id(pk)
        if not appointment:
            raise NotFound("Appointment not found.")

        serializer = AppointmentNotesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated = AppointmentService.update_notes(
                pk,
                serializer.validated_data['notes'],
                request.user
            )
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(AppointmentReadSerializer(updated).data)

    def destroy(self, request, pk=None):
        """
        DELETE /appointments/{id}/
        Soft deletes an appointment and marks it cancelled.
        - Doctors can only cancel their own appointments
        - Admins and receptionists can cancel any appointment
        - Completed appointments cannot be deleted
        """
        try:
            AppointmentService.soft_delete_appointment(pk, request.user)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(
            {'detail': 'Appointment cancelled successfully.'},
            status=status.HTTP_200_OK
        )