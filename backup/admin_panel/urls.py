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