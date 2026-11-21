from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Address, User


class RegisterForm(UserCreationForm):
    become_vendor = forms.BooleanField(required=False, label="I also want to sell on this marketplace")
    store_name = forms.CharField(required=False, max_length=120, help_text="Required if you want to sell")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        if data.get("become_vendor") and not data.get("store_name"):
            self.add_error("store_name", "Please choose a store name.")
        return data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email is used by another account.")
        return email


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ("full_name", "phone", "line1", "line2", "city", "state", "postal_code", "country", "is_default")
