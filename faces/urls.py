from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuthorizedFaceViewSet

router = DefaultRouter()
router.register(r'', AuthorizedFaceViewSet, basename='face')

urlpatterns = [
    path('', include(router.urls)),
]