from rest_framework.permissions import BasePermission


class IsDoctorOrAdmin(BasePermission):
    """
    Allows access only to doctors or admins.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        return request.user.role in ["doctor", "admin"]