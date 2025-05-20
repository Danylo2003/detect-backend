from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserRegisterView, UserLoginView, UserLogoutView,
    UserDetailsView, ChangePasswordView
)

urlpatterns = [
    # Authentication routes
    path('register/', UserRegisterView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User profile routes
    path('user/', UserDetailsView.as_view(), name='user_details'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('test-register/', UserRegisterView.as_view(), name='test_register'),
]
print(f"Accounts urlpatterns: {urlpatterns}")