from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """
    Allows access only to admin users.
    Used for staff management endpoints — creating, updating,
    deactivating doctor and receptionist accounts.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsAdminOrSelf(BasePermission):
    """
    Allows access if the user is an admin, or if they are
    accessing/modifying their own record.
    Used for profile and password change endpoints.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return (
            request.user.role == 'admin' or
            request.user == obj
        )


class IsDoctor(BasePermission):
    """
    Allows access only to doctor users.
    Used for clinical endpoints — writing medical notes,
    updating diagnoses, and managing prescriptions.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'doctor'
        )


class IsAdminDoctorOrReceptionist(BasePermission):
    """
    Allows access to any authenticated staff member.
    Used for read-only staff listing (e.g. receptionist
    needs to pick a doctor when booking an appointment).
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in ('admin', 'doctor', 'receptionist')
        )