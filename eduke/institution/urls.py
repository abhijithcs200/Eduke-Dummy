from django.urls import path
from . import views

app_name = 'institution'

urlpatterns = [
    path('login/', views.institution_login, name='login'),
    path('register/', views.institution_register, name='register'),
    path('dashboard/', views.institution_dashboard, name='dashboard'),
    path('profile/', views.institution_profile, name='profile'),
    path('classes/', views.institution_classes, name='classes'),
    path('edit-class/<int:class_id>/', views.edit_class, name='edit_class'),
    path('delete-class/<int:class_id>/', views.confrim_delete, name='delete_class'),
    path('classes/<int:class_id>/', views.class_details, name='class_details'),
    path('students/', views.institution_student, name='manage_student'),
    path('subjects/', views.institution_subjects, name='subjects'),
    path('subject/edit/<int:subject_id>/', views.edit_subject, name='edit_subject'),
    path('subject/delete/<int:subject_id>/', views.delete_subject, name='delete_subject'),
    path('student/edit/<int:student_id>/', views.edit_student, name='edit_student'),
    path('student/delete/<int:student_id>/', views.delete_student, name='delete_student'),
    path('api/get-next-roll/', views.get_next_roll_no, name='get_next_roll'),
    path('api/update-class-mappings/', views.update_class_name_mappings, name='update_class_mappings'),
    path('api/get-missing-mappings/', views.get_missing_mappings, name='get_missing_mappings'),
    path('security-checkup/', views.security_checkup, name='security_checkup')
]