from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.utils import rate_limited

from .forms import AddressForm, ProfileForm, RegisterForm


class RateLimitedLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if rate_limited(request, "login", limit=10, window=900):
            messages.error(request, "Too many login attempts. Please try again in 15 minutes.")
            return self.get(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and not rate_limited(request, "register", limit=10, window=3600) and form.is_valid():
        user = form.save()
        if form.cleaned_data.get("become_vendor"):
            from vendors.models import Vendor
            Vendor.objects.create(user=user, store_name=form.cleaned_data["store_name"])
            messages.info(request, "Your store application is pending admin approval.")
        login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
        messages.success(request, "Welcome aboard! Your account has been created.")
        return redirect(request.GET.get("next") or "home")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def addresses(request):
    form = AddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        addr = form.save(commit=False)
        addr.user = request.user
        if not request.user.addresses.exists():
            addr.is_default = True
        addr.save()
        messages.success(request, "Address saved.")
        return redirect("addresses")
    return render(request, "accounts/addresses.html", {"form": form, "addresses": request.user.addresses.all()})


@login_required
@require_POST
def address_delete(request, pk):
    get_object_or_404(request.user.addresses, pk=pk).delete()
    messages.info(request, "Address removed.")
    return redirect("addresses")


@login_required
@require_POST
def address_default(request, pk):
    addr = get_object_or_404(request.user.addresses, pk=pk)
    addr.is_default = True
    addr.save()
    return redirect("addresses")


@login_required
def notifications(request):
    items = list(request.user.notifications.all()[:50])
    return render(request, "accounts/notifications.html", {"items": items})


@login_required
@require_POST
def notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notifications")
