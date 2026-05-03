from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import User, PatientProfile, Message

admin.site.register(User)
admin.site.register(PatientProfile)
admin.site.register(Message)