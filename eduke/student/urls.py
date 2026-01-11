from django.urls import path
from . import views

app_name = 'student'

urlpatterns = [
    path('login/', views.student_login, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
]
