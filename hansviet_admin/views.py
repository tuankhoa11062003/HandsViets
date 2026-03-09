from datetime import datetime
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    NewsArticleForm,
    NewsCategoryForm,
    ServiceCategoryForm,
    ServiceForm,
)
from .models import NewsArticle, NewsCategory, Service, ServiceCategory


def staff_required(view_func):
    """Ensure user is staff/superuser and authenticated."""
    check_staff = user_passes_test(lambda u: u.is_staff or u.is_superuser, login_url="/auth/login/")
    return login_required(check_staff(view_func), login_url="/auth/login/")


@staff_required
def dashboard_home(request):
    context = {
        "total_users": 5,
        "total_videos": 12,
        "total_news": 3,
        "total_therapies": 4,
    }
    return render(request, "dashboard/index.html", context)


@staff_required
def user_list(request):
    User = get_user_model()
    role_filter = request.GET.get("role")
    qs = User.objects.all()
    if role_filter == "staff":
        qs = qs.filter(is_staff=True)
    elif role_filter == "user":
        qs = qs.filter(is_staff=False, is_superuser=False)

    users = [
        SimpleNamespace(
            pk=u.pk,
            username=u.username,
            email=u.email,
            role="staff" if u.is_staff or u.is_superuser else "user",
            is_active=u.is_active,
            date_joined=u.date_joined,
        )
        for u in qs.order_by("-date_joined")
    ]
    return render(request, "dashboard/users/list.html", {"users": users, "current_role": role_filter})


@staff_required
def user_edit(request, pk):
    User = get_user_model()
    user_obj = User.objects.filter(pk=pk).first()
    if user_obj:
        user = SimpleNamespace(
            pk=user_obj.pk,
            username=user_obj.username,
            email=user_obj.email,
            role="staff" if user_obj.is_staff or user_obj.is_superuser else "user",
        )
    else:
        user = None
    return render(request, "dashboard/users/form.html", {"target_user": user})


@staff_required
def user_delete(request, pk):
    User = get_user_model()
    user_obj = User.objects.filter(pk=pk).first()
    return render(request, "dashboard/users/confirm_delete.html", {"target_user": user_obj})


# Categories
@staff_required
def category_list(request):
    categories = list(ServiceCategory.objects.all())
    return render(request, "dashboard/categories/list.html", {"categories": categories})


@staff_required
def category_create(request):
    form = ServiceCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã tạo chuyên mục.")
        return redirect("dashboard:category_list")
    return render(request, "dashboard/categories/form.html", {"form": form, "title": "Thêm chuyên mục", "button_text": "Lưu"})


@staff_required
def category_edit(request, pk):
    category = get_object_or_404(ServiceCategory, pk=pk)
    form = ServiceCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật chuyên mục.")
        return redirect("dashboard:category_list")
    return render(request, "dashboard/categories/form.html", {"form": form, "title": "Chỉnh sửa chuyên mục", "button_text": "Lưu"})


@staff_required
def category_delete(request, pk):
    category = get_object_or_404(ServiceCategory, pk=pk)
    if request.method == "POST":
        category.delete()
        messages.success(request, "Đã xóa chuyên mục.")
        return redirect("dashboard:category_list")
    return render(request, "dashboard/categories/confirm_delete.html", {"category": category})


# Services
@staff_required
def service_list(request):
    categories = list(ServiceCategory.objects.all())
    services = list(Service.objects.select_related("category").all())
    return render(request, "dashboard/services/list.html", {"services": services, "categories": categories})


@staff_required
def service_create(request):
    form = ServiceForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã tạo dịch vụ.")
        return redirect("dashboard:service_list")
    categories = list(ServiceCategory.objects.all())
    return render(request, "dashboard/services/form.html", {"categories": categories, "form": form, "title": "Thêm dịch vụ", "button_text": "Lưu"})


@staff_required
def service_edit(request, pk):
    categories = list(ServiceCategory.objects.all())
    service = get_object_or_404(Service.objects.select_related("category"), pk=pk)
    form = ServiceForm(request.POST or None, request.FILES or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật dịch vụ.")
        return redirect("dashboard:service_list")
    return render(
        request,
        "dashboard/services/form.html",
        {"service": service, "categories": categories, "form": form, "title": "Chỉnh sửa dịch vụ", "button_text": "Lưu"},
    )


@staff_required
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == "POST":
        service.delete()
        messages.success(request, "Đã xóa dịch vụ.")
        return redirect("dashboard:service_list")
    return render(request, "dashboard/services/confirm_delete.html", {"service": service})


# News
@staff_required
def news_list(request):
    articles = list(NewsArticle.objects.select_related("category", "author").all())
    return render(request, "dashboard/news/list.html", {"articles": articles})


@staff_required
def news_create(request):
    form = NewsArticleForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã tạo bài viết.")
        return redirect("dashboard:news_list")
    categories = list(NewsCategory.objects.all())
    return render(request, "dashboard/news/form.html", {"categories": categories, "form": form, "title": "Thêm bài viết", "button_text": "Lưu"})


@staff_required
def news_edit(request, pk):
    categories = list(NewsCategory.objects.all())
    article = get_object_or_404(NewsArticle.objects.select_related("category"), pk=pk)
    form = NewsArticleForm(request.POST or None, request.FILES or None, instance=article)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật bài viết.")
        return redirect("dashboard:news_list")
    return render(request, "dashboard/news/form.html", {"article": article, "categories": categories, "form": form, "title": "Chỉnh sửa bài viết", "button_text": "Lưu"})


@staff_required
def news_delete(request, pk):
    article = get_object_or_404(NewsArticle, pk=pk)
    if request.method == "POST":
        article.delete()
        messages.success(request, "Đã xóa bài viết.")
        return redirect("dashboard:news_list")
    return render(request, "dashboard/news/confirm_delete.html", {"article": article})


@staff_required
def news_category_list(request):
    categories = list(NewsCategory.objects.all())
    return render(request, "dashboard/news/category_list.html", {"categories": categories})


@staff_required
def news_category_create(request):
    form = NewsCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã tạo chuyên mục tin.")
        return redirect("dashboard:news_category_list")
    return render(request, "dashboard/news/category_form.html", {"form": form, "title": "Thêm chuyên mục", "button_text": "Lưu"})


@staff_required
def news_category_edit(request, pk):
    category = get_object_or_404(NewsCategory, pk=pk)
    form = NewsCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật chuyên mục tin.")
        return redirect("dashboard:news_category_list")
    return render(request, "dashboard/news/category_form.html", {"form": form, "title": "Chỉnh sửa chuyên mục", "button_text": "Lưu"})


@staff_required
def news_category_delete(request, pk):
    category = get_object_or_404(NewsCategory, pk=pk)
    if request.method == "POST":
        category.delete()
        messages.success(request, "Đã xóa chuyên mục tin.")
        return redirect("dashboard:news_category_list")
    return render(request, "dashboard/news/category_confirm_delete.html", {"category": category})
