from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from .views import StreamingViewSet

router = DefaultRouter()
router.register(r'', StreamingViewSet, basename='streaming')

urlpatterns = [
    path('', include(router.urls)),
]