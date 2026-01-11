from django.contrib import admin
from . models import Institution, Classes, User, Students, ClassNameMapping

# Register your models here.

admin.site.register(Institution)
admin.site.register(Classes)
admin.site.register(User)
admin.site.register(Students)
admin.site.register(ClassNameMapping)