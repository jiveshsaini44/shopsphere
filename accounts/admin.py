from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Address, Notification, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "phone", "is_staff", "date_joined")
    fieldsets = UserAdmin.fieldsets + (("Extra", {"fields": ("phone",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + ((None, {"fields": ("email",)}),)
    search_fields = ("username", "email", "phone")


admin.site.register(Address)
admin.site.register(Notification)
