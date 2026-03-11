from datetime import datetime
from types import SimpleNamespace

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator

from .forms import (
    DashboardUserCreateForm,
    DashboardUserUpdateForm,
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
    admin_login_url = getattr(settings, "ADMIN_LOGIN_URL", "/hansviet_admin/login/")
    check_staff = user_passes_test(lambda u: u.is_staff or u.is_superuser, login_url=admin_login_url)
    return login_required(check_staff(view_func), login_url=admin_login_url)


def admin_login_view(request):
    """Dedicated login screen for staff/admin users."""
    default_next = "/hansviet_admin/"
    next_url = request.GET.get("next") or request.POST.get("next") or default_next

    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect(next_url)
        messages.error(request, "Tai khoan hien tai khong co quyen quan tri.")
        return redirect("/")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            if user.is_staff or user.is_superuser:
                login(request, user)
                return redirect(next_url)
            messages.error(request, "Tai khoan nay khong co quyen quan tri.")
        else:
            messages.error(request, "Ten dang nhap hoac mat khau khong dung.")

    return render(request, "admin/admin_login.html", {"form": form, "next": next_url})


def dashboard_logout(request):
    logout(request)
    admin_login_url = getattr(settings, "ADMIN_LOGIN_URL", "/hansviet_admin/login/")
    return redirect(f"{admin_login_url}?next=/hansviet_admin/")


def _greeting_by_local_time():
    hour = timezone.localtime().hour
    if 5 <= hour < 12:
        return "Chào buổi sáng"
    if 12 <= hour < 18:
        return "Chào buổi chiều"
    return "Chào buổi tối"


def _initials(text):
    raw = (text or "").strip()
    if not raw:
        return "NA"
    parts = [part for part in raw.replace("_", " ").split() if part]
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    return raw[:2].upper()


def _relative_time_label(dt):
    if not dt:
        return "Vừa xong"
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    seconds = max(int((timezone.now() - dt).total_seconds()), 0)
    if seconds < 60:
        return "Vừa xong"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} phút trước"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} giờ trước"
    days = hours // 24
    if days < 7:
        return f"{days} ngày trước"
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M")


def _event_sort_key(dt):
    if not dt:
        return 0
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt.timestamp()


@staff_required
def dashboard_home(request):
    User = get_user_model()
    today = timezone.localdate()
    news_today = NewsArticle.objects.filter(is_published=True, published_at__date=today).count()
    leads_today = Lead.objects.filter(created_at__date=today).count()

    on_duty_qs = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True), is_active=True).order_by("-last_login", "username")
    on_duty_count = on_duty_qs.count()
    on_duty_badges = [_initials(user.get_full_name() or user.username) for user in on_duty_qs[:3]]
    on_duty_extra_count = max(on_duty_count - len(on_duty_badges), 0)

    events = []

    for article in NewsArticle.objects.filter(is_published=True).order_by("-published_at")[:6]:
        events.append(
            {
                "event_time": article.published_at,
                "title": "Bản tin mới",
                "description": f'Đã đăng bài "{article.title}".',
                "dot_class": "bg-teal-100",
            }
        )

    for lead in Lead.objects.order_by("-created_at")[:6]:
        lead_contact = lead.email or lead.phone or lead.name
        source_page = lead.page or "website"
        events.append(
            {
                "event_time": lead.created_at,
                "title": "Yêu cầu hỗ trợ mới",
                "description": f"{lead_contact} vừa gửi yêu cầu từ trang {source_page}.",
                "dot_class": "bg-blue-100",
            }
        )

    for user_obj in User.objects.filter(is_staff=False, is_superuser=False).order_by("-date_joined")[:6]:
        user_contact = user_obj.email or user_obj.username
        events.append(
            {
                "event_time": user_obj.date_joined,
                "title": "Người dùng mới",
                "description": f"{user_contact} vừa đăng ký tài khoản.",
                "dot_class": "bg-amber-100",
            }
        )

    recent_activities = sorted(events, key=lambda item: _event_sort_key(item.get("event_time")), reverse=True)[:6]
    for item in recent_activities:
        item["time_label"] = _relative_time_label(item.get("event_time"))

    context = {
        "total_users": User.objects.count(),
        "total_videos": Video.objects.count(),
        "total_news": NewsArticle.objects.count(),
        "total_therapies": Package.objects.filter(is_active=True).count(),
        "total_services": Service.objects.count(),
        "new_news_today": news_today,
        "new_leads_today": leads_today,
        "greeting_text": _greeting_by_local_time(),
        "on_duty_count": on_duty_count,
        "on_duty_badges": on_duty_badges,
        "on_duty_extra_count": on_duty_extra_count,
        "recent_activities": recent_activities,
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
def user_create(request):
    form = DashboardUserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        created_user = form.save()
        messages.success(request, f'Đã tạo tài khoản "{created_user.username}".')
        return redirect("dashboard:user_list")

    return render(
        request,
        "dashboard/users/form.html",
        {
            "form": form,
            "title": "Thêm nhân viên",
            "button_text": "Tạo tài khoản",
            "is_create": True,
        },
    )


@staff_required
def user_edit(request, pk):
    User = get_user_model()
    user_obj = get_object_or_404(User, pk=pk)
    form = DashboardUserUpdateForm(request.POST or None, instance=user_obj)

    if request.method == "POST" and form.is_valid():
        if request.user.pk == user_obj.pk:
            role = form.cleaned_data.get("role")
            is_active = form.cleaned_data.get("is_active")
            if role != "staff":
                form.add_error("role", "Không thể hạ quyền chính tài khoản đang đăng nhập.")
            if not is_active:
                form.add_error("is_active", "Không thể khóa chính tài khoản đang đăng nhập.")

        if not form.errors:
            form.save()
            messages.success(request, "Đã cập nhật tài khoản.")
            return redirect("dashboard:user_list")

    return render(
        request,
        "dashboard/users/form.html",
        {
            "form": form,
            "target_user": user_obj,
            "title": f"Chỉnh sửa: {user_obj.username}",
            "button_text": "Lưu",
            "is_create": False,
        },
    )


@staff_required
def user_delete(request, pk):
    User = get_user_model()
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if request.user.pk == user_obj.pk:
            messages.error(request, "Không thể xóa chính tài khoản đang đăng nhập.")
            return redirect("dashboard:user_list")
        username = user_obj.username
        user_obj.delete()
        messages.success(request, f'Đã xóa tài khoản "{username}".')
        return redirect("dashboard:user_list")
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
    category_slug = (request.GET.get("category") or "").strip()
    page_number = request.GET.get("page")
    articles_qs = NewsArticle.objects.select_related("category", "author").all().order_by("-published_at", "-id")
    if category_slug:
        articles_qs = articles_qs.filter(category__slug=category_slug)
    paginator = Paginator(articles_qs, 12)
    page_obj = paginator.get_page(page_number)
    categories = list(NewsCategory.objects.all().order_by("name"))
    return render(
        request,
        "dashboard/news/list.html",
        {
            "articles": page_obj.object_list,
            "page_obj": page_obj,
            "categories": categories,
            "current_category": category_slug,
        },
    )


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
