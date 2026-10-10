from rest_framework.permissions import BasePermission


class IsQuizOwner(BasePermission):
    """Only the owner may read, change or delete a quiz (otherwise 403)."""

    message = 'You do not have permission to access this quiz.'

    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id
