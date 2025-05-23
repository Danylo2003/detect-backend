# admin_panel/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserAdminViewSet, SystemStatusViewSet,
    SubscriptionViewSet, SystemSettingViewSet
)

router = DefaultRouter()
router.register(r'users', UserAdminViewSet, basename='admin-user')
router.register(r'system-status', SystemStatusViewSet, basename='system-status')
router.register(r'subscription', SubscriptionViewSet, basename='subscription')
router.register(r'settings', SystemSettingViewSet, basename='settings')

urlpatterns = [
    path('', include(router.urls)),
]

# The router will automatically create these endpoints:
# GET    /admin/users/                    - List users
# POST   /admin/users/                    - Create user
# GET    /admin/users/{id}/               - Retrieve user
# PUT    /admin/users/{id}/               - Update user
# PATCH  /admin/users/{id}/               - Partial update user
# DELETE /admin/users/{id}/               - Delete user
# POST   /admin/users/{id}/block/         - Block user
# POST   /admin/users/{id}/unblock/       - Unblock user
# POST   /admin/users/{id}/activate/      - Activate user
# POST   /admin/users/{id}/deactivate/    - Deactivate user
# POST   /admin/users/{id}/update_status/ - Update user status