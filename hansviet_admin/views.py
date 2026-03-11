from datetime import datetime
import hashlib
import re
from types import SimpleNamespace

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.core.mail import send_mail

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
from .models import Lead, NewsArticle, NewsCategory, Package, Purchase, Service, ServiceCategory, Video


def staff_required(view_func):
    """Ensure user is staff/superuser and authenticated."""
    admin_login_url = getattr(settings, "ADMIN_LOGIN_URL", "/hansviet_admin/login/")
    check_staff = user_passes_test(lambda u: u.is_staff or u.is_superuser, login_url=admin_login_url)
    return login_required(check_staff(view_func), login_url=admin_login_url)


def _safe_admin_next(request):
    fallback = "/hansviet_admin/"
    candidate = request.GET.get("next") or request.POST.get("next") or ""
    if not candidate:
        return fallback
    if not url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return fallback
    if not candidate.startswith("/hansviet_admin/"):
        return fallback
    return candidate


def admin_login_view(request):
    """Dedicated login screen for staff/admin users."""
    next_url = _safe_admin_next(request)

    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect(next_url)
        messages.error(request, "Tai khoan nay khong co quyen vao trang admin.")
        return redirect(settings.LOGIN_URL)

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            if user.is_staff or user.is_superuser:
                login(request, user)
                return redirect(next_url)
            messages.error(request, "Trang nay chi danh cho tai khoan admin.")
            return redirect(settings.LOGIN_URL)
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


def _service_package_slug(service_slug: str) -> str:
    base = f"svc-{service_slug}"
    if len(base) <= 50:
        return base
    digest = hashlib.sha1(service_slug.encode("utf-8")).hexdigest()[:8]
    return f"svc-{service_slug[:37]}-{digest}"


def _extract_booking_meta_from_message(message_text: str) -> dict:
    text = (message_text or "").strip()
    if not text:
        return {
            "appointment_date": "",
            "specialty": "",
            "service_name": "",
            "note": "",
        }

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    appointment_date = ""
    specialty = ""
    service_name = ""
    note_lines = []

    for line in lines:
        date_match = re.match(r"^-+\s*Ngày khám mong muốn:\s*(.+)$", line, flags=re.IGNORECASE)
        if date_match:
            appointment_date = date_match.group(1).strip()
            continue

        specialty_match = re.match(r"^-+\s*Chuyên khoa:\s*(.+)$", line, flags=re.IGNORECASE)
        if specialty_match:
            specialty = specialty_match.group(1).strip()
            continue

        service_match = re.match(r"^-+\s*Dịch vụ quan tâm:\s*(.+)$", line, flags=re.IGNORECASE)
        if service_match:
            service_name = service_match.group(1).strip()
            continue

        if line.lower().startswith("thông tin đặt lịch:"):
            continue
        note_lines.append(line)

    return {
        "appointment_date": appointment_date,
        "specialty": specialty,
        "service_name": service_name,
        "note": "\n".join(note_lines).strip(),
    }


def _decorate_booking_lead(lead: Lead) -> Lead:
    legacy_meta = _extract_booking_meta_from_message(lead.message or "")
    lead.display_booking_date = (
        lead.booking_date.strftime("%d/%m/%Y")
        if lead.booking_date
        else legacy_meta.get("appointment_date") or "Chưa chọn"
    )
    lead.display_booking_specialty = lead.booking_specialty or legacy_meta.get("specialty") or "Chưa chọn"
    lead.display_booking_service = lead.booking_service or legacy_meta.get("service_name") or "Chưa chọn"
    lead.display_note = legacy_meta.get("note") or "Không có ghi chú thêm."
    lead.display_created_at = timezone.localtime(lead.created_at).strftime("%d/%m/%Y %H:%M")
    lead.display_ack_sent_at = (
        timezone.localtime(lead.booking_ack_sent_at).strftime("%d/%m/%Y %H:%M")
        if lead.booking_ack_sent_at
        else ""
    )
    lead.can_send_ack = bool((lead.email or "").strip())
    return lead


def _booking_queryset_with_filters(request):
    q = (request.GET.get("q") or "").strip()
    specialty = (request.GET.get("specialty") or "").strip()
    date_from_raw = (request.GET.get("date_from") or "").strip()
    date_to_raw = (request.GET.get("date_to") or "").strip()

    bookings_qs = Lead.objects.filter(page="booking").order_by("-created_at")
    if q:
        bookings_qs = bookings_qs.filter(
            Q(name__icontains=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
            | Q(message__icontains=q)
        )
    if specialty:
        bookings_qs = bookings_qs.filter(booking_specialty__iexact=specialty)

    warnings = []
    if date_from_raw:
        try:
            date_from = datetime.strptime(date_from_raw, "%Y-%m-%d").date()
            bookings_qs = bookings_qs.filter(booking_date__gte=date_from)
        except ValueError:
            warnings.append("Ngày bắt đầu không hợp lệ. Vui lòng dùng định dạng YYYY-MM-DD.")
    if date_to_raw:
        try:
            date_to = datetime.strptime(date_to_raw, "%Y-%m-%d").date()
            bookings_qs = bookings_qs.filter(booking_date__lte=date_to)
        except ValueError:
            warnings.append("Ngày kết thúc không hợp lệ. Vui lòng dùng định dạng YYYY-MM-DD.")

    filters = {
        "q": q,
        "specialty": specialty,
        "date_from_raw": date_from_raw,
        "date_to_raw": date_to_raw,
    }
    return bookings_qs, filters, warnings


def _send_booking_confirmation_email(lead: Lead) -> tuple[bool, str]:
    to_email = (lead.email or "").strip()
    if not to_email:
        return False, "Khách hàng chưa có email để gửi xác nhận."

    lead = _decorate_booking_lead(lead)
    subject = "HandsViet xác nhận đã nhận lịch đặt khám"
    body = (
        f"Chào {lead.name},\n\n"
        "HandsViet xác nhận đã nhận được lịch đặt khám của bạn.\n\n"
        "Thông tin lịch hẹn:\n"
        f"- Ngày khám mong muốn: {lead.display_booking_date}\n"
        f"- Chuyên khoa: {lead.display_booking_specialty}\n"
        f"- Dịch vụ: {lead.display_booking_service}\n"
        f"- Ghi chú: {lead.display_note}\n"
        f"- Thời gian gửi yêu cầu: {lead.display_created_at}\n\n"
        "Bộ phận CSKH sẽ chủ động liên hệ với bạn để xác nhận khung giờ cụ thể.\n\n"
        "Trân trọng,\n"
        "HandsViet."
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", ""),
            recipient_list=[to_email],
            fail_silently=False,
        )
        lead.booking_ack_sent_at = timezone.now()
        lead.save(update_fields=["booking_ack_sent_at"])
        return True, ""
    except Exception as exc:
        return False, str(exc)


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
    package_slugs = [_service_package_slug(service.slug) for service in services]
    sold_by_slug = dict(
        Purchase.objects.exclude(status="canceled")
        .filter(package__slug__in=package_slugs)
        .values("package__slug")
        .annotate(total=Count("id"))
        .values_list("package__slug", "total")
    )
    for service in services:
        service.sold_count = int(sold_by_slug.get(_service_package_slug(service.slug), 0))
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
def booking_list(request):
    bookings_qs, filters, warnings = _booking_queryset_with_filters(request)
    page_number = request.GET.get("page")
    for warning in warnings:
        messages.warning(request, warning)

    page_obj = Paginator(bookings_qs, 20).get_page(page_number)
    bookings = list(page_obj.object_list)
    for index, lead in enumerate(bookings):
        bookings[index] = _decorate_booking_lead(lead)

    total_bookings = Lead.objects.filter(page="booking").count()
    today_bookings = Lead.objects.filter(page="booking", created_at__date=timezone.localdate()).count()
    specialty_options = list(
        Lead.objects.filter(page="booking")
        .exclude(booking_specialty="")
        .order_by()
        .values_list("booking_specialty", flat=True)
        .distinct()
    )
    latest_booking_id = int(bookings[0].id) if bookings else 0

    return render(
        request,
        "dashboard/bookings/list.html",
        {
            "bookings": bookings,
            "page_obj": page_obj,
            "total_bookings": total_bookings,
            "today_bookings": today_bookings,
            "specialty_options": specialty_options,
            "current_q": filters["q"],
            "current_specialty": filters["specialty"],
            "current_date_from": filters["date_from_raw"],
            "current_date_to": filters["date_to_raw"],
            "latest_booking_id": latest_booking_id,
            "realtime_enabled": True,
        },
    )


@staff_required
def booking_feed(request):
    bookings_qs, _, _ = _booking_queryset_with_filters(request)
    try:
        last_id = int(request.GET.get("last_id") or 0)
    except ValueError:
        last_id = 0

    new_rows_qs = bookings_qs.filter(id__gt=last_id).order_by("id")
    rows = []
    latest_id = last_id

    for lead in new_rows_qs:
        decorated = _decorate_booking_lead(lead)
        latest_id = max(latest_id, int(decorated.id))
        rows.append(
            {
                "id": decorated.id,
                "name": decorated.name,
                "phone": decorated.phone or "",
                "email": decorated.email or "",
                "booking_date": decorated.display_booking_date,
                "booking_specialty": decorated.display_booking_specialty,
                "booking_service": decorated.display_booking_service,
                "note": decorated.display_note,
                "created_at_text": decorated.display_created_at,
                "ack_sent_at": decorated.display_ack_sent_at,
                "can_send_ack": decorated.can_send_ack,
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "latest_id": latest_id,
            "new_count": len(rows),
            "rows": rows,
            "total_bookings": Lead.objects.filter(page="booking").count(),
            "today_bookings": Lead.objects.filter(page="booking", created_at__date=timezone.localdate()).count(),
            "server_time": timezone.localtime().strftime("%d/%m/%Y %H:%M:%S"),
        }
    )


@staff_required
def booking_send_confirmation_email(request, pk):
    lead = get_object_or_404(Lead, pk=pk, page="booking")
    if request.method != "POST":
        return redirect("dashboard:booking_list")

    success, error_message = _send_booking_confirmation_email(lead)
    if success:
        messages.success(request, f"Đã gửi email xác nhận tới {lead.email}.")
    else:
        messages.error(request, f"Gửi email thất bại: {error_message}")

    redirect_url = (request.POST.get("next") or "").strip()
    if redirect_url and redirect_url.startswith("/hansviet_admin/"):
        return redirect(redirect_url)
    return redirect("dashboard:booking_list")


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
