from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import EmailAuthenticationForm, ProfileForm
from .permissions import member_required


def _safe_redirect_target(request: HttpRequest) -> str:
    redirect_to = request.POST.get("next") or request.GET.get("next") or settings.LOGIN_REDIRECT_URL
    if url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return settings.LOGIN_REDIRECT_URL


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == "POST":
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user is not None:
                login(request, user)
                return redirect(_safe_redirect_target(request))
    else:
        form = EmailAuthenticationForm(request)

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": _safe_redirect_target(request)},
    )


@require_POST
def logout_view(request: HttpRequest) -> HttpResponseRedirect:
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


@member_required
def profile_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST" and request.POST.get("action") == "password":
        profile_form = ProfileForm(user=request.user)
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed.")
            return redirect("accounts:profile")
    elif request.method == "POST":
        profile_form = ProfileForm(request.POST, request.FILES, user=request.user)
        password_form = PasswordChangeForm(user=request.user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Profile saved.")
            return redirect("accounts:profile")
    else:
        profile_form = ProfileForm(user=request.user)
        password_form = PasswordChangeForm(user=request.user)

    return render(
        request,
        "accounts/profile.html",
        {"profile_form": profile_form, "password_form": password_form},
    )
