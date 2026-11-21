from django import forms

from .models import Order


class CheckoutForm(forms.Form):
    address_id = forms.IntegerField(required=False)
    full_name = forms.CharField(max_length=120, required=False)
    phone = forms.CharField(max_length=20, required=False)
    line1 = forms.CharField(max_length=200, required=False)
    line2 = forms.CharField(max_length=200, required=False)
    city = forms.CharField(max_length=100, required=False)
    state = forms.CharField(max_length=100, required=False)
    postal_code = forms.CharField(max_length=20, required=False)
    country = forms.CharField(max_length=100, required=False, initial="United States")
    save_address = forms.BooleanField(required=False)
    payment_method = forms.ChoiceField(choices=Order.PAYMENT_METHODS)

    def clean(self):
        data = super().clean()
        if not data.get("address_id"):
            for f in ("full_name", "phone", "line1", "city", "postal_code"):
                if not data.get(f):
                    self.add_error(f, "This field is required.")
        return data


class ReturnForm(forms.Form):
    reason = forms.CharField(max_length=300)


class MockPayForm(forms.Form):
    card_number = forms.CharField(max_length=24)
    name = forms.CharField(max_length=80)
    expiry = forms.CharField(max_length=7)
    cvc = forms.CharField(max_length=4)
