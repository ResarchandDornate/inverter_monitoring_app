from django.urls import path
from .views import SigninView,PermissionView, SignupView, verifyOTP, SendOTP, FetchUserView, ResetPasswordView, ConfirmResetPasswordView


urlpatterns = [
    path('signin/', SigninView.as_view()),
    path('signup/',  SignupView.as_view()),
    path('verify-otp/',  verifyOTP.as_view()),
    path('send-otp/',  SendOTP.as_view()),
    path('fetch-user/',  FetchUserView.as_view()),
    path('reset-password/',  ResetPasswordView.as_view(), name='reset-password'),
    path('confirm-reset-password/',  ConfirmResetPasswordView.as_view(), name='reset-password'),
    path('permissions/', PermissionView.as_view(), name='permissions'),
]
