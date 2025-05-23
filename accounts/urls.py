# accounts/urls.py - Fixed version with separate views

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserRegisterView, UserLoginView, UserLogoutView,
    UserDetailsView, ChangePasswordView,
    DeactivateAccountView, ReactivateAccountView
)

urlpatterns = [
    # Authentication routes
    path('register/', UserRegisterView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User profile routes
    path('user/', UserDetailsView.as_view(), name='user_details'),
    path('user/deactivate/', DeactivateAccountView.as_view(), name='deactivate_account'),
    path('user/reactivate/', ReactivateAccountView.as_view(), name='reactivate_account'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('test-register/', UserRegisterView.as_view(), name='test_register'),
]