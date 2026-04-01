from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


User = get_user_model()


def _can_manage_users(user):
    return user.is_superuser or user.role in {"Admin", "Management"}


@login_required
def user_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, "You do not have permission to manage users.")
        return redirect("dashboard_home")

    users = User.objects.all().order_by("username")
    return render(request, "users/user_list.html", {"users": users, "role_choices": User.ROLE_CHOICES})


@login_required
def user_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, "You do not have permission to create users.")
        return redirect("dashboard_home")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        role = (request.POST.get("role") or "Viewer").strip()
        phone = (request.POST.get("phone") or "").strip()
        employee_id = (request.POST.get("employee_id") or "").strip()
        password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm_password") or ""
        is_staff = request.POST.get("is_staff") == "on"

        if not username or not password or not confirm_password:
            messages.error(request, "Username, password, and confirm password are required.")
        elif password != confirm_password:
            messages.error(request, "Password and confirm password do not match.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
        elif role not in dict(User.ROLE_CHOICES):
            messages.error(request, "Selected role is invalid.")
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                phone=phone,
                employee_id=employee_id,
                is_staff=is_staff,
            )
            messages.success(request, f"User {user.username} created successfully.")
            return redirect("users:user_list")

    return render(request, "users/user_create.html", {"role_choices": User.ROLE_CHOICES})
