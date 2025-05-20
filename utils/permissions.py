from rest_framework import permissions

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins to access it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Check if the user is an admin
        if request.user.is_admin():
            return True
        
        # Check if the object has a user attribute and if it equals the request user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # If the object is a user, check if it is the request user
        if hasattr(obj, 'email'):
            return obj == request.user
        
        return False

class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin users to access the view.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin()

class IsManagerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow managers or admins to access the view.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_admin() or request.user.is_manager()