from django.db import models

# Create your models here.

class User(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('class_head', 'Class Head'),
        ('subject_head', 'Subject Head'),
        ('parent', 'Parent'),
    ]

    id = models.BigAutoField(primary_key=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    def __str__(self):
        return self.role

class Institution(models.Model):
    institution_id = models.BigAutoField(primary_key=True)
    email = models.EmailField(unique=True)
    institution_name = models.CharField(max_length=191)
    password = models.CharField(max_length=191)
    abbreviation = models.CharField(max_length=50, unique=True, null=True,)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.abbreviation

class Classes(models.Model):
    id = models.BigAutoField(primary_key=True)
    class_name = models.CharField(max_length=191)
    class_head = models.CharField(max_length=191)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=191)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.class_name
    
class Students(models.Model):
    id = models.BigAutoField(primary_key=True)
    roll_no = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.CharField(max_length=191, unique=True, blank=True, null=True)
    password = models.CharField(max_length=50)
    class_obj = models.ForeignKey(Classes, on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
class Subjects(models.Model):
    id = models.BigAutoField(primary_key=True)
    subject_name = models.CharField(max_length=191)
    subject_head = models.CharField(max_length=191)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=191)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    class_obj = models.ForeignKey(Classes, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.subject_name
        

class ClassNameMapping(models.Model):
    id = models.BigAutoField(primary_key=True)
    class_name_keywords = models.TextField(help_text="Comma-separated keywords for this class type")
    abbreviation = models.CharField(max_length=10, help_text="Abbreviation for this class type")
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, help_text="Institution this mapping belongs to")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.class_name_keywords} -> {self.abbreviation}"
        
    



