from rest_framework import permissions

class CanEditDocument(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role.can_edit

class CanApproveDocument(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role.can_approve

class CanSignDocument(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role.can_sign
