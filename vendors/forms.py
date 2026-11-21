from django import forms

from catalog.models import Product, ProductImage, ProductVariant

from .models import Vendor


class VendorApplyForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ("store_name", "description", "support_email")


class StoreSettingsForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ("store_name", "description", "logo", "support_email")


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("name", "category", "description", "price", "compare_at_price", "stock", "sku", "image", "is_active")

    def clean(self):
        data = super().clean()
        price, compare = data.get("price"), data.get("compare_at_price")
        if price is not None and price <= 0:
            self.add_error("price", "Price must be greater than zero.")
        if price and compare and compare <= price:
            self.add_error("compare_at_price", "Original price must be higher than the selling price.")
        return data


class VariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ("name", "sku", "price_delta", "stock")


class ImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ("image", "alt")


class ShipForm(forms.Form):
    status = forms.ChoiceField(choices=[("processing", "processing"), ("shipped", "shipped"),
                                        ("delivered", "delivered"), ("cancelled", "cancelled")])
    carrier = forms.CharField(max_length=60, required=False)
    tracking_number = forms.CharField(max_length=80, required=False)


class PayoutForm(forms.Form):
    amount = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
