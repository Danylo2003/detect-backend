from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationSettingViewSet

router = DefaultRouter()
router.register(r'', NotificationSettingViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
]