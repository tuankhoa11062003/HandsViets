import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import HttpResponse

from django.views.decorators.csrf import csrf_exempt
from hansviet_admin.models import (
    Lead,
    NewsArticle,
    NewsCategory,
    Package,
    Purchase,
    Service,
    ServiceCategory,
    Video,
)
from .forms import LeadForm

DEFAULT_NEWS_CATEGORIES = [
    ("Tin tức Y khoa", "tin-tuc-y-khoa"),
    ("Câu chuyện khách hàng", "cau-chuyen-khach-hang"),
    ("Tin truyền thông", "tin-truyen-thong"),
    ("Tư vấn PHCN", "tu-van-phcn"),
    ("Khuyến mãi sự kiện", "khuyen-mai-su-kien"),
]


def ensure_news_categories():
    for name, slug in DEFAULT_NEWS_CATEGORIES:
        NewsCategory.objects.get_or_create(slug=slug, defaults={"name": name})


def _handle_lead(request, page_slug):
    """Create Lead from simple public form."""
    form = LeadForm(request.POST or None, initial={"page": page_slug})
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã nhận thông tin, chúng tôi sẽ liên hệ sớm.")
        return True, form
    return False, form


def _user_can_view_paid(user):
    """Check if user has an active purchase."""
    if not user.is_authenticated:
        return False
    return Purchase.objects.filter(
        user=user, status="active", expires_at__gt=timezone.now()
    ).exists()


def home(request):
    return render(request, "pages/home.html")


def about(request):
    return render(request, "pages/about.html")


def booking(request):
    saved, form = _handle_lead(request, "booking")
    if saved:
        return redirect(request.path)
    return render(request, "pages/booking.html", {"lead_form": form})


def contact(request):
    saved, form = _handle_lead(request, "contact")
    if saved:
        return redirect(request.path)
    return render(request, "pages/contact.html", {"lead_form": form})


def exercise_library(request):
    can_paid = _user_can_view_paid(request.user)
    videos = Video.objects.filter(is_active=True).select_related("category").order_by("title")
    free_videos = [v for v in videos if v.access == Video.ACCESS_FREE]
    paid_videos = [v for v in videos if v.access == Video.ACCESS_PAID]
    # Build category list for legacy template filters
    category_names = sorted({(v.category.name if v.category else "Khác") for v in videos})
    exercises = [{"category": name, "videos": []} for name in category_names]
    return render(
        request,
        "pages/exercise_library.html",
        {
            "free_videos": free_videos,
            "paid_videos": paid_videos,
            "can_watch_paid": can_paid,
            "exercises": exercises,
        },
    )


def experts(request):
    return render(request, "pages/experts.html")


def facilities(request):
    return render(request, "pages/facilities.html")


def faq(request):
    return render(request, "pages/faq.html")


def news_list(request, category_slug=None):
    ensure_news_categories()
    qs = NewsArticle.objects.filter(is_published=True).select_related("category", "author")
    current_category = None
    if category_slug:
        current_category = get_object_or_404(NewsCategory, slug=category_slug)
        qs = qs.filter(category=current_category)
    context = {
        "current_category": current_category,
        "featured_news": qs.first(),
        "articles": qs[1:],
        "categories": NewsCategory.objects.all(),
    }
    return render(request, "pages/news.html", context)


def news_category(request, category_slug):
    ensure_news_categories()
    return news_list(request, category_slug=category_slug)


def news_detail(request, slug=None):
    article = get_object_or_404(
        NewsArticle.objects.select_related("category", "author"),
        slug=slug,
        is_published=True,
    )
    related = (
        NewsArticle.objects.filter(category=article.category, is_published=True)
        .exclude(pk=article.pk)
        .order_by("-published_at")[:3]
    )
    return render(request, "pages/news_detail.html", {"article": article, "related_articles": related})


def occupational_therapy(request):
    return render(request, "pages/occupational_therapy.html")


def partners(request):
    return render(request, "pages/partners.html")


def physical_therapy(request):
    return render(request, "pages/physical_therapy.html")


def rehab_fields(request):
    return render(request, "pages/rehab_fields.html")


def services(request):
    categories = ServiceCategory.objects.all()
    services = Service.objects.select_related("category").all()
    return render(
        request,
        "pages/services.html",
        {"categories": categories, "services": services, "category": None},
    )


def services_temp(request):
    return render(request, "pages/services_temp.html")


def category_detail(request, slug):
    category = get_object_or_404(ServiceCategory, slug=slug)
    services = Service.objects.select_related("category").filter(category=category)
    categories = ServiceCategory.objects.all()
    context = {"category": category, "services": services, "categories": categories}
    return render(request, "pages/services.html", context)


def service_detail(request, slug):
    service = get_object_or_404(Service.objects.select_related("category"), slug=slug)
    return render(request, "pages/service_detail.html", {"service": service, "template_exists": True})


def speech_therapy(request):
    return render(request, "pages/speech_therapy.html")


def visit_guide(request):
    return render(request, "pages/visit_guide.html")


def buy_package(request, slug):
    package = get_object_or_404(Package, slug=slug, is_active=True)
    if not request.user.is_authenticated:
        messages.error(request, "Vui lòng đăng nhập để mua gói.")
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")
    if request.method == "POST":
        expires = timezone.now() + timedelta(days=package.duration_days)
        Purchase.objects.create(
            user=request.user,
            package=package,
            expires_at=expires,
            status="active",
        )
        messages.success(request, "Đã kích hoạt gói.")
        return redirect("/exercise-library/")
    return render(request, "pages/package_buy.html", {"package": package})


@csrf_exempt
def login_view(request):
    """
    Simple username/password login using Django's AuthenticationForm.
    Supports ?next= redirect. Session luôn hết khi đóng trình duyệt.
    """
    if request.user.is_authenticated:
        target = request.GET.get("next") or (
            settings.LOGIN_REDIRECT_URL
            if request.user.is_staff or request.user.is_superuser
            else "/"
        )
        return redirect(target)

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Luôn hết hạn khi đóng trình duyệt
            request.session.set_expiry(0)

            target = request.GET.get("next") or (
                settings.LOGIN_REDIRECT_URL if user.is_staff or user.is_superuser else "/"
            )
            return redirect(target)
        else:
            messages.error(request, "Tên đăng nhập hoặc mật khẩu không đúng.")

    return render(request, "auth/login.html", {"form": form})


def register_view(request):
    """
    Minimal registration: collects username, email, password, password_confirm.
    Creates a new user then logs them in.
    """
    if request.user.is_authenticated:
        return redirect("/")

    form_data = {
        "username": "",
        "email": "",
    }
    errors = {}

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        password_confirm = request.POST.get("password_confirm") or ""

        form_data["username"] = username
        form_data["email"] = email

        if not username:
            errors["username"] = "Vui lòng nhập tên đăng nhập."
        elif len(username) < 3:
            errors["username"] = "Tên đăng nhập phải có ít nhất 3 ký tự."
        elif User.objects.filter(username__iexact=username).exists():
            errors["username"] = "Tên đăng nhập đã tồn tại. Hãy chọn tên khác."

        if not email:
            errors["email"] = "Vui lòng nhập email."

        if not password:
            errors["password"] = "Vui lòng nhập mật khẩu."
        elif len(password) < 6:
            errors["password"] = "Mật khẩu phải có ít nhất 6 ký tự."

        if password != password_confirm:
            errors["password_confirm"] = "Mật khẩu xác nhận không khớp."

        if not errors:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            login(request, user)
            messages.success(request, "Đăng ký thành công!")
            return redirect("/")

    return render(request, "auth/register.html", {"form_data": form_data, "errors": errors})


def logout_view(request):
    """
    Allow logout via GET (and POST) then redirect home.
    """
    logout(request)
    return redirect("/")


# VNPay stub handlers
def vnpay_start(request, slug):
    """
    Khởi tạo thanh toán VNPay (stub). Cần bổ sung cấu hình merchant + ký HMAC.
    """
    package = get_object_or_404(Package, slug=slug, is_active=True)
    txn_ref = uuid.uuid4().hex[:12]
    Transaction = None  # placeholder to avoid import loop if unused
    # TODO: tạo Transaction entry và build URL VNPay
    messages.info(request, "VNPay chưa được cấu hình. Vui lòng hoàn tất tích hợp.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


def vnpay_return(request):
    """
    Điểm nhận callback/return từ VNPay. Cần verify signature + cập nhật Transaction/Purchase.
    """
    return HttpResponse("VNPay return placeholder")
