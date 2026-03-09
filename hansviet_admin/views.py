from datetime import datetime
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    NewsArticleForm,
    NewsCategoryForm,
    PackageForm,
    ServiceCategoryForm,
    ServiceForm,
    VideoForm,
)
from .models import Lead, NewsArticle, NewsCategory, Package, Service, ServiceCategory, Video


def staff_required(view_func):
    """Ensure user is staff/superuser and authenticated."""
    check_staff = user_passes_test(lambda u: u.is_staff or u.is_superuser, login_url="/auth/login/")
    return login_required(check_staff(view_func), login_url="/auth/login/")


@staff_required
def dashboard_home(request):
    User = get_user_model()
    today = timezone.localdate()

    context = {
        "total_users": User.objects.count(),
        "total_videos": Video.objects.count(),
        "total_news": NewsArticle.objects.count(),
        "total_therapies": Package.objects.filter(is_active=True).count(),
        "total_services": Service.objects.count(),
        "new_news_today": NewsArticle.objects.filter(published_at__date=today).count(),
        "new_leads_today": Lead.objects.filter(created_at__date=today).count(),
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


@staff_required
def video_list(request):
    access_filter = request.GET.get("access")
    videos_qs = Video.objects.select_related("category").all()
    if access_filter in {Video.ACCESS_FREE, Video.ACCESS_PAID}:
        videos_qs = videos_qs.filter(access=access_filter)
    videos = list(videos_qs.order_by("title"))
    return render(
        request,
        "dashboard/videos/list.html",
        {
            "videos": videos,
            "current_access": access_filter or "",
            "total_videos": Video.objects.count(),
            "total_free": Video.objects.filter(access=Video.ACCESS_FREE).count(),
            "total_paid": Video.objects.filter(access=Video.ACCESS_PAID).count(),
        },
    )


@staff_required
def video_create(request):
    form = VideoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã tạo video bài tập.")
        return redirect("dashboard:video_list")
    return render(request, "dashboard/videos/form.html", {"form": form, "title": "Thêm video", "button_text": "Lưu"})


@staff_required
def video_edit(request, pk):
    video = get_object_or_404(Video, pk=pk)
    form = VideoForm(request.POST or None, instance=video)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật video.")
        return redirect("dashboard:video_list")
    return render(
        request,
        "dashboard/videos/form.html",
        {"form": form, "video": video, "title": "Chỉnh sửa video", "button_text": "Lưu"},
    )


@staff_required
def video_delete(request, pk):
    video = get_object_or_404(Video, pk=pk)
    if request.method == "POST":
        video.delete()
        messages.success(request, "Đã xóa video.")
        return redirect("dashboard:video_list")
    return render(request, "dashboard/videos/confirm_delete.html", {"video": video})


@staff_required
def therapy_list(request):
    status_filter = request.GET.get("status")
    packages_qs = Package.objects.all()
    if status_filter == "active":
        packages_qs = packages_qs.filter(is_active=True)
    elif status_filter == "inactive":
        packages_qs = packages_qs.filter(is_active=False)
    packages = list(packages_qs.order_by("name"))
    return render(
        request,
        "dashboard/therapies/list.html",
        {
            "packages": packages,
            "current_status": status_filter or "",
            "total_packages": Package.objects.count(),
            "total_active": Package.objects.filter(is_active=True).count(),
            "total_inactive": Package.objects.filter(is_active=False).count(),
        },
    )


@staff_required
def therapy_create(request):
    form = PackageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã tạo gói liệu pháp.")
        return redirect("dashboard:therapy_list")
    return render(
        request,
        "dashboard/therapies/form.html",
        {"form": form, "title": "Thêm liệu pháp", "button_text": "Lưu"},
    )


@staff_required
def therapy_edit(request, pk):
    package = get_object_or_404(Package, pk=pk)
    form = PackageForm(request.POST or None, instance=package)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật gói liệu pháp.")
        return redirect("dashboard:therapy_list")
    return render(
        request,
        "dashboard/therapies/form.html",
        {"form": form, "package": package, "title": "Chỉnh sửa liệu pháp", "button_text": "Lưu"},
    )


@staff_required
def therapy_delete(request, pk):
    package = get_object_or_404(Package, pk=pk)
    if request.method == "POST":
        package.delete()
        messages.success(request, "Đã xóa gói liệu pháp.")
        return redirect("dashboard:therapy_list")
    return render(request, "dashboard/therapies/confirm_delete.html", {"package": package})


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
