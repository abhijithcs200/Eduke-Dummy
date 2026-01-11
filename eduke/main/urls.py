from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('user-portal/', views.user_portal, name='user_portal'),
    path('logout/', views.logout, name='logout'),
    path('<str:user_type>/forgot-password/', views.forgot_password, name='forgot_password'),
    path('<str:user_type>/verify-otp/', views.verify_otp, name='verify_otp'),
    path('<str:user_type>/reset-password/', views.reset_password, name='reset_password'),
    path('contact-email/', views.contact_email, name='contact_email'),
    path('institution/', include('institution.urls')),
    path('student/', include('student.urls')),
]