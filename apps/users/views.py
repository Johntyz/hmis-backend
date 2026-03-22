from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework import status

from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import (
    StaffCreateSerializer,
    StaffUpdateSerializer,
    StaffReadSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    AdminPasswordResetSerializer,
)
from .services import UserService
from .permissions import IsAdmin


# ─────────────────────────────────────────────
# AUTH VIEWS
# ─────────────────────────────────────────────

class LoginView(APIView):
    """
    POST /auth/login/
    Authenticates a staff member and returns JWT tokens
    along with basic user info for the frontend.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        user = authenticate(username=username, password=password)

        if user is None:
            return Response(
                {'detail': 'Invalid credentials.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'detail': 'This account has been deactivated.'},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name(),
                'role': user.role if not user.is_superuser else 'admin',
                'email': user.email,
            }
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /auth/logout/
    Blacklists the refresh token, preventing further use.
    Requires rest_framework_simplejwt.token_blacklist in INSTALLED_APPS.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {'detail': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {'detail': 'Invalid or expired token.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {'detail': 'Logged out successfully.'},
            status=status.HTTP_200_OK
        )


class MeView(APIView):
    """
    GET  /auth/me/   → returns the authenticated user's profile
    PATCH /auth/me/  → updates the authenticated user's own profile
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = StaffReadSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = StaffUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # BUG FIX: update_staff returns the updated instance.
            # The original code returned StaffReadSerializer(request.user).data
            # which reads stale data from the request object, not the DB.
            updated_user = UserService.update_staff(
                request.user.id, serializer.validated_data
            )
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(StaffReadSerializer(updated_user).data)


class ChangePasswordView(APIView):
    """
    POST /auth/change-password/
    Allows the authenticated user to change their own password.
    Requires the current password to verify identity.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            UserService.change_password(
                user=request.user,
                old_password=serializer.validated_data['old_password'],
                new_password=serializer.validated_data['new_password'],
            )
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response({'detail': 'Password changed successfully.'})


# ─────────────────────────────────────────────
# STAFF MANAGEMENT VIEWS (Admin only)
# ─────────────────────────────────────────────

class StaffViewSet(ViewSet):
    """
    Admin-only ViewSet for managing doctor and receptionist accounts.

    Endpoints:
        GET    /staff/              → list all active staff
        POST   /staff/              → create a new doctor or receptionist
        GET    /staff/{id}/         → retrieve a staff member
        PATCH  /staff/{id}/         → update a staff member
        DELETE /staff/{id}/         → deactivate (soft delete) a staff member
        POST   /staff/{id}/reset-password/ → admin resets a staff member's password
    """
    permission_classes = [IsAdmin]

    def list(self, request):
        """GET /staff/ — list all active staff members."""
        staff = UserService.list_staff()
        return Response(StaffReadSerializer(staff, many=True).data)

    def retrieve(self, request, pk=None):
        """GET /staff/{id}/ — retrieve a single staff member."""
        user = UserService.get_staff_by_id(pk)
        if not user:
            raise NotFound("Staff member not found.")
        return Response(StaffReadSerializer(user).data)

    def create(self, request):
        """POST /staff/ — create a new doctor or receptionist."""
        serializer = StaffCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = UserService.create_staff(serializer.validated_data)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(
            StaffReadSerializer(user).data,
            status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, pk=None):
        """PATCH /staff/{id}/ — update a staff member's details."""
        user = UserService.get_staff_by_id(pk)
        if not user:
            raise NotFound("Staff member not found.")

        serializer = StaffUpdateSerializer(user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated_user = UserService.update_staff(pk, serializer.validated_data)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        return Response(StaffReadSerializer(updated_user).data)

    def destroy(self, request, pk=None):
        """DELETE /staff/{id}/ — deactivate (soft delete) a staff member."""
        try:
            UserService.deactivate_staff(pk)
        except ValueError as e:
            raise NotFound({'detail': str(e)})

        return Response(
            {'detail': 'Staff member deactivated successfully.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        """
        POST /staff/{id}/reset-password/
        Admin resets a staff member's password without requiring the old one.
        Used for locked-out accounts.
        """
        serializer = AdminPasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            UserService.reset_password(
                pk, serializer.validated_data['new_password']
            )
        except ValueError as e:
            raise NotFound({'detail': str(e)})

        return Response(
            {'detail': 'Password reset successfully.'},
            status=status.HTTP_200_OK
        )