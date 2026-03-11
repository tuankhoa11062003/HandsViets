import uuid
import re
import json
import hashlib
import logging
import unicodedata
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from datetime import datetime
from urllib.parse import parse_qs, quote, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import get_language
from django.http import Http404, HttpResponse, JsonResponse
from django.db.models import F
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.urls import reverse

from django.views.decorators.csrf import csrf_exempt
from hansviet_admin.models import (
    ExerciseLog,
    ExerciseProfile,
    Lead,
    NewsArticle,
    NewsCategory,
    Package,
    PatientProfile,
    ProgressNote,
    Purchase,
    Service,
    ServiceCategory,
    SessionSchedule,
    Transaction,
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

NEWS_HERO_DESCRIPTIONS = {
    "tin-tuc-y-khoa": "Cập nhật kiến thức y khoa, xu hướng điều trị và các nghiên cứu hữu ích cho phục hồi chức năng.",
    "cau-chuyen-khach-hang": "Những câu chuyện phục hồi thực tế từ bệnh nhân và gia đình, truyền cảm hứng mỗi ngày.",
    "tin-truyen-thong": "Thông tin báo chí, hoạt động truyền thông và các dấu mốc nổi bật của HandsViet.",
    "tu-van-phcn": "Góc tư vấn chuyên môn về phục hồi chức năng: triệu chứng, lộ trình và cách chăm sóc đúng.",
    "khuyen-mai-su-kien": "Thông báo ưu đãi, workshop, sự kiện cộng đồng và chương trình đồng hành cùng người bệnh.",
}

DEFAULT_SERVICE_CATEGORIES = [
    ("PHCN Co Xuong Khop", "co-xuong-khop"),
    ("PHCN Chan Thuong Chinh Hinh", "chan-thuong-chinh-hinh"),
    ("PHCN Ton Thuong Than Kinh", "than-kinh"),
    ("PHCN Sau Tai Bien", "sau-tai-bien"),
    ("PHCN Sau Phau Thuat", "sau-phau-thuat"),
    ("Tim Mach", "tim-mach"),
    ("Nhi Khoa", "nhi-khoa"),
    ("Vat Ly Tri Lieu", "vat-ly-tri-lieu"),
    ("Hoat Dong Tri Lieu", "hoat-dong-tri-lieu"),
    ("Ngon Ngu Tri Lieu", "ngon-ngu-tri-lieu"),
    ("Dinh Duong", "dinh-duong"),
]

SERVICE_CYCLE_META = {
    "week": {"rank": 0, "label": "tuần", "group": "Gói theo tuần"},
    "month": {"rank": 1, "label": "tháng", "group": "Gói theo tháng"},
    "year": {"rank": 2, "label": "năm", "group": "Gói theo năm"},
    "other": {"rank": 3, "label": "", "group": "Gói khác"},
}

PAYMENT_TIMEOUT_SECONDS = 180
PAYMENT_REF_PATTERN = re.compile(r"(HV[A-Z0-9]{10,})")
BOOKING_SPECIALTY_LABELS = {
    "xuong-khop": "PHCN Cơ xương khớp",
    "chan-thuong": "PHCN Chấn thương",
    "than-kinh": "PHCN Thần kinh",
    "nhi-khoa": "PHCN Nhi khoa",
}
BOOKING_SERVICE_LABELS = {
    "bai-tap": "Bài tập trị liệu",
    "vat-ly": "Vật lý trị liệu",
    "hoat-dong": "Hoạt động trị liệu",
    "ngon-ngu": "Ngôn ngữ trị liệu",
}

logger = logging.getLogger(__name__)

REHAB_FIELD_DETAILS = {
    "co-xuong-khop": {
        "title": "Phục hồi cơ xương khớp",
        "subtitle": "Dành cho thoái hóa khớp, đau cột sống, viêm quanh khớp, hội chứng quá tải vận động.",
        "image": "https://images.unsplash.com/photo-1576091160550-21735999181c?auto=format&fit=crop&q=80&w=1400",
        "overview": "Lĩnh vực phục hồi cơ xương khớp tại HandsViet tập trung vào giảm đau, phục hồi tầm vận động và nâng cao chất lượng sinh hoạt. Chương trình được xây dựng theo mức độ tổn thương và đặc thù nghề nghiệp của từng người bệnh.",
        "highlights": [
            "Đánh giá vận động và mức độ đau theo từng giai đoạn.",
            "Phác đồ tập luyện cá nhân hóa theo mục tiêu phục hồi.",
            "Kết hợp vật lý trị liệu để giảm đau và cải thiện biên độ khớp.",
        ],
        "conditions": ["Thoái hóa cột sống cổ/lưng", "Đau vai gáy, viêm quanh khớp vai", "Đau gối, thoái hóa khớp gối", "Hội chứng ống cổ tay"],
        "methods": ["Tập trị liệu vận động", "Điện xung, siêu âm trị liệu", "Manual therapy", "Hướng dẫn tư thế và phòng ngừa tái phát"],
        "process": ["Khám đánh giá ban đầu", "Đặt mục tiêu theo tuần", "Can thiệp tại cơ sở + bài tập tại nhà", "Tái khám và điều chỉnh phác đồ"],
        "outcomes": ["Giảm đau rõ sau 2-4 tuần", "Tăng linh hoạt và sức mạnh cơ", "Cải thiện khả năng lao động"],
        "faqs": [
            {"q": "Cần tập bao lâu?", "a": "Thông thường 6-12 tuần, tùy mức độ tổn thương và mục tiêu phục hồi."},
            {"q": "Có cần dùng thuốc không?", "a": "Phác đồ ưu tiên tập và vật lý trị liệu, thuốc chỉ dùng khi có chỉ định bác sĩ."},
        ],
        "gallery": [
            "https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&q=80&w=1200",
            "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?auto=format&fit=crop&q=80&w=1200",
        ],
    },
    "chan-thuong-chinh-hinh": {
        "title": "Phục hồi chấn thương chỉnh hình",
        "subtitle": "Đồng hành sau gãy xương, đứt dây chằng, chấn thương thể thao.",
        "image": "https://images.unsplash.com/photo-1597452485669-2c7bb5fef90d?auto=format&fit=crop&q=80&w=1400",
        "overview": "Lĩnh vực này hướng đến khôi phục vận động sau chấn thương và phẫu thuật chỉnh hình. Chương trình có lộ trình rõ ràng theo từng mốc lành thương mô mềm, xương và dây chằng.",
        "highlights": [
            "Kiểm soát đau và phù nề sau chấn thương.",
            "Tập mạnh cơ - ổn định khớp theo từng mốc phục hồi.",
            "Hướng dẫn quay lại sinh hoạt và thể thao an toàn.",
        ],
        "conditions": ["Gay xuong sau bat bot/ket xuong", "Rach day chang cheo", "Tran thuong co khop do the thao", "Sau noi soi khop goi/vai"],
        "methods": ["Tập phục hồi theo giai đoạn", "Bài tập proprioception", "Tập trở lại chạy nhảy đổi hướng", "Đánh giá biomechanics khi quay lại thể thao"],
        "process": ["Đánh giá ROM và sức mạnh", "Tập phục hồi vận động nền", "Tập chuyên sâu theo môn thể thao", "Kiểm tra sẵn sàng quay lại thi đấu"],
        "outcomes": ["Giảm nguy cơ tái chấn thương", "Trở lại tập luyện an toàn", "Cải thiện sức bền và phản xạ"],
        "faqs": [
            {"q": "Sau mo bao lau thi tap?", "a": "Tuy loai mo, nhung nen bat dau som theo huong dan bac si va ky thuat vien."},
            {"q": "Có cần ngừng chơi thể thao?", "a": "Không cần ngừng hoàn toàn, sẽ có lộ trình tập thay thế phù hợp."},
        ],
        "gallery": [
            "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&q=80&w=1200",
            "https://images.unsplash.com/photo-1576671494903-8ec23c1f97f2?auto=format&fit=crop&q=80&w=1200",
        ],
    },
    "than-kinh": {
        "title": "Phục hồi tổn thương thần kinh",
        "subtitle": "Áp dụng cho bệnh nhân sau đột quỵ, tổn thương tủy sống, liệt dây thần kinh.",
        "image": "https://images.unsplash.com/photo-1559757175-5700dde675bc?auto=format&fit=crop&q=80&w=1400",
        "overview": "Phục hồi thần kinh cần cách tiếp cận đa chuyên khoa và theo dõi liên tục. HandsViet kết hợp tập vận động, tập cân bằng và huấn luyện kỹ năng sinh hoạt để tăng mức độ độc lập cho người bệnh.",
        "highlights": [
            "Đánh giá chức năng vận động, thăng bằng và sinh hoạt hằng ngày.",
            "Tập tái học vận động theo nguyên tắc phục hồi thần kinh.",
            "Phoi hop gia dinh de duy tri tap luyen tai nha.",
        ],
        "conditions": ["Sau dot quy", "Liet day than kinh ngoai bien", "Ton thuong tuy song", "Roi loan thang bang va dang di"],
        "methods": ["Task-oriented training", "Tập thăng bằng và phân bố trọng lượng", "Tập ADL", "Hướng dẫn người chăm sóc"],
        "process": ["Đánh giá MMT, Berg, FIM", "Đặt mục tiêu chức năng", "Can thiệp đa mô hình", "Đánh giá lại định kỳ 2-4 tuần"],
        "outcomes": ["Cải thiện khả năng tự chăm sóc", "Tăng độ an toàn khi di chuyển", "Giảm nguy cơ té ngã và biến chứng"],
        "faqs": [
            {"q": "Dot quy lau nam co tap duoc khong?", "a": "Van co the cai thien neu tap dung muc tieu va duy tri deu dan."},
            {"q": "Gia dinh can lam gi?", "a": "Gia dinh dong vai tro lon trong viec ho tro tap tai nha va du phong bien chung."},
        ],
        "gallery": [
            "https://images.unsplash.com/photo-1579154204601-01588f351e67?auto=format&fit=crop&q=80&w=1200",
            "https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&q=80&w=1200",
        ],
    },
    "sau-tai-bien": {
        "title": "Phục hồi sau tai biến",
        "subtitle": "Can thiệp sớm để cải thiện vận động, ngôn ngữ và độc lập sinh hoạt.",
        "image": "https://images.unsplash.com/photo-1584982751601-97dcc096659c?auto=format&fit=crop&q=80&w=1400",
        "overview": "Trạng thái sau tai biến cần chương trình phục hồi toàn diện và kịp thời. HandsViet xây dựng lộ trình chi tiết theo mức độ tổn thương, tình trạng tim mạch và mục tiêu của gia đình.",
        "highlights": [
            "Đánh giá toàn diện chức năng ngay từ giai đoạn đầu.",
            "Xây dựng lộ trình phục hồi theo mục tiêu ngắn hạn và dài hạn.",
            "Hướng dẫn chăm sóc và phòng tái biến tại nhà.",
        ],
        "conditions": ["Yếu/liệt nửa người", "Rối loạn ngôn ngữ sau tai biến", "Nuốt nghẹn", "Giảm trí nhớ sau tai biến"],
        "methods": ["Tập chuyển đổi tư thế", "Tập đi với dụng cụ hỗ trợ", "Tập ngôn ngữ trị liệu phối hợp", "Tư vấn dinh dưỡng và dự phòng tái biến"],
        "process": ["Sàng lọc nguy cơ và mức độ phụ thuộc", "Can thiệp hằng ngày", "Đánh giá lại hằng tuần", "Lập kế hoạch duy trì sau xuất viện"],
        "outcomes": ["Tăng khả năng tự lập", "Cải thiện giao tiếp và vận động", "Giảm tái nhập viện do biến chứng"],
        "faqs": [
            {"q": "Bao lau thay tien bo?", "a": "Tien bo thuong thay ro sau 2-6 tuan neu tap deu va dung phac do."},
            {"q": "Co tap tai nha duoc khong?", "a": "Co, nhung can duoc huong dan bai ban va theo doi dinh ky."},
        ],
        "gallery": [
            "https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&q=80&w=1200",
            "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&q=80&w=1200",
        ],
    },
    "sau-phau-thuat": {
        "title": "Phục hồi sau phẫu thuật",
        "subtitle": "Dành cho người bệnh sau thay khớp, phẫu thuật cột sống, phẫu thuật dây chằng.",
        "image": "https://images.unsplash.com/photo-1581056771107-24ca5f033742?auto=format&fit=crop&q=80&w=1400",
        "overview": "Sau phẫu thuật, phục hồi đúng thời điểm giúp rút ngắn thời gian hồi phục và hạn chế biến chứng. HandsViet theo sát từng giai đoạn để bảo đảm an toàn và hiệu quả.",
        "highlights": [
            "Giảm đau, giảm co cứng và cải thiện tầm vận động sớm.",
            "Tập điểm tuần tự theo chỉ định hậu phẫu.",
            "Theo dõi sát tiến độ để trở lại sinh hoạt bình thường.",
        ],
        "conditions": ["Sau thay khớp háng/gối", "Sau mổ dây chằng", "Sau mổ cột sống", "Sau kết hợp xương"],
        "methods": ["Tập thở và vận động sớm", "Tập ROM có kiểm soát", "Tập mạnh cơ trung tâm và chi", "Hướng dẫn phòng ngừa huyết khối và té ngã"],
        "process": ["Khám hậu phẫu và sàng lọc nguy cơ", "Can thiệp theo mốc 1-3-6-12 tuần", "Đánh giá chức năng theo mục tiêu", "Bàn giao chương trình duy trì dài hạn"],
        "outcomes": ["Rút ngắn thời gian hồi phục", "Tăng biên độ khớp và sức mạnh", "Trở lại sinh hoạt và công việc sớm hơn"],
        "faqs": [
            {"q": "Sau mổ có nên nằm nghỉ nhiều?", "a": "Không. Vận động sớm đúng cách giúp giảm biến chứng và hồi phục nhanh hơn."},
            {"q": "Khi nào có thể lái xe/làm việc?", "a": "Tùy loại mổ và nghề nghiệp, sẽ được đánh giá theo mốc tái khám."},
        ],
        "gallery": [
            "https://images.unsplash.com/photo-1580281657527-47e49f3f5f0f?auto=format&fit=crop&q=80&w=1200",
            "https://images.unsplash.com/photo-1538108149393-fbbd81895907?auto=format&fit=crop&q=80&w=1200",
        ],
    },
}


def ensure_news_categories():
    for name, slug in DEFAULT_NEWS_CATEGORIES:
        category, _ = NewsCategory.objects.get_or_create(slug=slug, defaults={"name": name})
        if category.name != name:
            category.name = name
            category.save(update_fields=["name"])


def ensure_service_categories():
    for index, (name, slug) in enumerate(DEFAULT_SERVICE_CATEGORIES):
        ServiceCategory.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "order": index},
        )


def _parse_service_cycle(duration_text: str) -> tuple[str, int]:
    text = (duration_text or "").strip().lower()
    normalized_text = "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )
    count_match = re.search(r"(\d+)", normalized_text)
    cycle_count = int(count_match.group(1)) if count_match else 1

    if any(token in normalized_text for token in ("tuan", "week", "wk")):
        return "week", max(1, cycle_count)
    if any(token in normalized_text for token in ("thang", "month", "mo")):
        return "month", max(1, cycle_count)
    if any(token in normalized_text for token in ("nam", "year", "yr")):
        return "year", max(1, cycle_count)
    return "other", max(1, cycle_count)


def _decorate_service(service: Service) -> Service:
    cycle_key, cycle_count = _parse_service_cycle(service.duration or "")
    meta = SERVICE_CYCLE_META.get(cycle_key, SERVICE_CYCLE_META["other"])

    service.cycle_key = cycle_key
    service.cycle_rank = int(meta["rank"])
    service.cycle_count = cycle_count
    service.cycle_group_label = str(meta["group"])
    service.display_price = (service.price_text or "").strip() or "Liên hệ"
    service.display_duration = (service.duration or "").strip() or "Chưa cập nhật"
    service.display_full_info = f"{service.display_price} / {service.display_duration}"
    return service


def _sorted_services(rows) -> list[Service]:
    decorated = [_decorate_service(service) for service in rows]
    return sorted(
        decorated,
        key=lambda service: (
            int(getattr(service, "cycle_rank", 9)),
            int(getattr(service, "cycle_count", 999)),
            int(service.order or 0),
            (service.title or "").lower(),
        ),
    )


def _group_services(rows) -> list[dict]:
    services = list(rows)
    if not services:
        return []
    if not hasattr(services[0], "cycle_key"):
        services = _sorted_services(services)

    groups = {key: [] for key in ("week", "month", "year", "other")}
    for service in services:
        groups.setdefault(service.cycle_key, []).append(service)

    out = []
    for key in ("week", "month", "year", "other"):
        items = groups.get(key) or []
        if not items:
            continue
        out.append(
            {
                "key": key,
                "label": SERVICE_CYCLE_META[key]["group"],
                "services": items,
            }
        )
    return out


def _parse_amount_text(value: str) -> Decimal:
    digits = re.sub(r"[^\d]", "", value or "")
    if not digits:
        return Decimal("0")
    return Decimal(digits)


def _duration_to_days(duration_text: str) -> int:
    cycle_key, cycle_count = _parse_service_cycle(duration_text or "")
    if cycle_key == "week":
        return max(1, cycle_count * 7)
    if cycle_key == "month":
        return max(1, cycle_count * 30)
    if cycle_key == "year":
        return max(1, cycle_count * 365)
    return max(1, cycle_count)


def _service_package_slug(service_slug: str) -> str:
    base = f"svc-{service_slug}"
    if len(base) <= 50:
        return base
    digest = hashlib.sha1(service_slug.encode("utf-8")).hexdigest()[:8]
    return f"svc-{service_slug[:37]}-{digest}"


def _sync_package_from_service(service: Service) -> Package:
    price = _parse_amount_text(service.price_text or "")
    if price <= 0:
        raise ValueError("Giá dịch vụ chưa hợp lệ để thanh toán.")

    duration_days = _duration_to_days(service.duration or "")
    package_slug = _service_package_slug(service.slug)
    defaults = {
        "name": service.title,
        "description": service.summary or f"Gói dịch vụ {service.title}",
        "duration_days": duration_days,
        "price": price,
        "is_active": True,
    }
    package, created = Package.objects.get_or_create(slug=package_slug, defaults=defaults)
    if created:
        return package

    update_fields = []
    if package.name != defaults["name"]:
        package.name = defaults["name"]
        update_fields.append("name")
    if package.description != defaults["description"]:
        package.description = defaults["description"]
        update_fields.append("description")
    if package.duration_days != defaults["duration_days"]:
        package.duration_days = defaults["duration_days"]
        update_fields.append("duration_days")
    if package.price != defaults["price"]:
        package.price = defaults["price"]
        update_fields.append("price")
    if not package.is_active:
        package.is_active = True
        update_fields.append("is_active")

    if update_fields:
        package.save(update_fields=update_fields)
    return package


def _generate_transaction_ref() -> str:
    while True:
        suffix = uuid.uuid4().hex[:4].upper()
        candidate = f"HV{timezone.now():%y%m%d%H%M%S}{suffix}"
        if not Transaction.objects.filter(txn_ref=candidate).exists():
            return candidate


def _transaction_deadline(txn: Transaction):
    return txn.created_at + timedelta(seconds=PAYMENT_TIMEOUT_SECONDS)


def _transaction_remaining_seconds(txn: Transaction) -> int:
    remaining = int((_transaction_deadline(txn) - timezone.now()).total_seconds())
    return max(0, remaining)


def _mark_transaction_failed(txn: Transaction, reason: str = "timeout") -> Transaction:
    if txn.status != "pending":
        return txn

    raw = dict(txn.raw_params or {})
    raw["failed_reason"] = reason
    raw["failed_at"] = timezone.now().isoformat()
    txn.status = "failed"
    txn.raw_params = raw
    txn.save(update_fields=["status", "raw_params"])

    Purchase.objects.filter(payment_ref=txn.txn_ref, status="active").update(
        status="canceled",
        expires_at=timezone.now(),
    )
    return txn


def _expire_transaction_if_needed(txn: Transaction) -> Transaction:
    if txn.status == "pending" and _transaction_remaining_seconds(txn) <= 0:
        return _mark_transaction_failed(txn, reason="timeout")
    return txn


def _activate_purchase_for_transaction(txn: Transaction) -> Purchase:
    now = timezone.now()
    expires = now + timedelta(days=max(1, int(txn.package.duration_days or 1)))
    purchase = Purchase.objects.filter(payment_ref=txn.txn_ref).first()
    if purchase:
        purchase.user = txn.user
        purchase.package = txn.package
        purchase.status = "active"
        purchase.expires_at = expires
        purchase.save(update_fields=["user", "package", "status", "expires_at"])
        return purchase

    return Purchase.objects.create(
        user=txn.user,
        package=txn.package,
        expires_at=expires,
        status="active",
        payment_ref=txn.txn_ref,
    )


def _extract_txn_ref_from_payload(payload: dict) -> str:
    direct_keys = ("txn_ref", "reference", "order_code", "payment_ref", "orderCode")
    for key in direct_keys:
        value = str(payload.get(key) or "").strip().upper()
        if value:
            return value

    text_keys = ("description", "content", "addInfo", "transferContent", "message", "note")
    for key in text_keys:
        text = str(payload.get(key) or "")
        match = PAYMENT_REF_PATTERN.search(text.upper())
        if match:
            return match.group(1)
    return ""


def _parse_payload_amount(payload: dict) -> Decimal | None:
    amount_candidates = (
        payload.get("amount"),
        payload.get("transferAmount"),
        payload.get("totalAmount"),
        payload.get("value"),
    )
    for candidate in amount_candidates:
        if candidate in ("", None):
            continue
        try:
            if isinstance(candidate, (int, float, Decimal)):
                return Decimal(str(candidate))
            cleaned = re.sub(r"[^\d]", "", str(candidate))
            if cleaned:
                return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            continue
    return None


def _build_transfer_content(package: Package, service: Service, txn_ref: str) -> str:
    duration_text = (service.duration or "").strip() or f"{package.duration_days} ngày"
    return f"{package.name} - {duration_text} - {txn_ref}"


def _build_vietqr_url(amount: Decimal, transfer_content: str) -> tuple[str, str]:
    bank_id = str(getattr(settings, "QR_BANK_ID", "") or "").strip()
    account_no = str(getattr(settings, "QR_ACCOUNT_NO", "") or "").strip()
    account_name = str(getattr(settings, "QR_ACCOUNT_NAME", "") or "").strip()
    if not bank_id or not account_no or not account_name:
        return "", "Thiếu cấu hình QR_BANK_ID / QR_ACCOUNT_NO / QR_ACCOUNT_NAME trong settings."

    amount_int = int(amount)
    info_q = quote(transfer_content, safe="")
    account_name_q = quote(account_name, safe="")
    url = (
        f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact2.png"
        f"?amount={amount_int}&addInfo={info_q}&accountName={account_name_q}"
    )
    return url, ""


def _parse_recipient_emails(value) -> list[str]:
    if isinstance(value, str):
        candidates = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        candidates = [str(item).strip() for item in value]
    else:
        candidates = [str(value).strip()] if value else []
    return [email for email in candidates if email]


def _send_email_safe(subject: str, body: str, recipients: list[str]) -> bool:
    to_emails = _parse_recipient_emails(recipients)
    if not to_emails:
        return False
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", ""),
            recipient_list=to_emails,
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Failed to send email '%s' to %s", subject, to_emails)
        return False


def _extract_booking_meta(post_data) -> dict:
    date_raw = (post_data.get("date") or "").strip()
    specialty_key = (post_data.get("specialty") or "").strip()
    service_key = (post_data.get("service") or "").strip()

    appointment_date_obj = None
    appointment_date = date_raw
    if date_raw:
        try:
            appointment_date_obj = datetime.strptime(date_raw, "%Y-%m-%d").date()
            appointment_date = appointment_date_obj.strftime("%d/%m/%Y")
        except ValueError:
            appointment_date = date_raw

    specialty = BOOKING_SPECIALTY_LABELS.get(specialty_key, specialty_key)
    service_name = BOOKING_SERVICE_LABELS.get(service_key, service_key)
    return {
        "appointment_date_obj": appointment_date_obj,
        "appointment_date": appointment_date,
        "specialty": specialty,
        "service_name": service_name,
    }


def _merge_booking_message(base_message: str, booking_meta: dict) -> str:
    lines = []
    if booking_meta.get("appointment_date"):
        lines.append(f"- Ngày khám mong muốn: {booking_meta['appointment_date']}")
    if booking_meta.get("specialty"):
        lines.append(f"- Chuyên khoa: {booking_meta['specialty']}")
    if booking_meta.get("service_name"):
        lines.append(f"- Dịch vụ quan tâm: {booking_meta['service_name']}")

    details_text = ""
    if lines:
        details_text = "Thông tin đặt lịch:\n" + "\n".join(lines)

    base = (base_message or "").strip()
    if base and details_text:
        return f"{base}\n\n{details_text}"
    if details_text:
        return details_text
    return base


def _send_booking_notifications(lead: Lead, booking_meta: dict):
    appointment_date = booking_meta.get("appointment_date") or "Chưa chọn"
    specialty = booking_meta.get("specialty") or "Chưa chọn"
    service_name = booking_meta.get("service_name") or "Chưa chọn"
    created_at_text = timezone.localtime(lead.created_at).strftime("%d/%m/%Y %H:%M")
    message_text = (lead.message or "").strip() or "Không có ghi chú thêm."

    user_email = (lead.email or "").strip()
    if user_email:
        user_subject = "HandsViet đã nhận yêu cầu đặt lịch khám của bạn"
        user_body = (
            f"Chào {lead.name},\n\n"
            "HandsViet đã nhận được yêu cầu đặt lịch khám của bạn.\n\n"
            f"Thông tin:\n"
            f"- Họ tên: {lead.name}\n"
            f"- Số điện thoại: {lead.phone or 'Chưa cập nhật'}\n"
            f"- Email: {user_email}\n"
            f"- Ngày khám mong muốn: {appointment_date}\n"
            f"- Chuyên khoa: {specialty}\n"
            f"- Dịch vụ quan tâm: {service_name}\n"
            f"- Ghi chú: {message_text}\n"
            f"- Thời gian gửi: {created_at_text}\n\n"
            "Bộ phận chăm sóc khách hàng sẽ liên hệ bạn sớm.\n"
            "HandsViet."
        )
        _send_email_safe(user_subject, user_body, [user_email])

    internal_recipients = _parse_recipient_emails(getattr(settings, "BOOKING_CONTACT_EMAIL", ""))
    if internal_recipients:
        internal_subject = f"[Booking] Yêu cầu mới từ {lead.name}"
        internal_body = (
            "Có yêu cầu đặt lịch khám mới từ website.\n\n"
            f"Thông tin khách:\n"
            f"- Họ tên: {lead.name}\n"
            f"- Số điện thoại: {lead.phone or 'Chưa cập nhật'}\n"
            f"- Email: {lead.email or 'Chưa cập nhật'}\n"
            f"- Ngày khám mong muốn: {appointment_date}\n"
            f"- Chuyên khoa: {specialty}\n"
            f"- Dịch vụ quan tâm: {service_name}\n"
            f"- Nguồn: {lead.page or 'booking'}\n"
            f"- Ghi chú: {message_text}\n"
            f"- Thời gian: {created_at_text}\n"
        )
        _send_email_safe(internal_subject, internal_body, internal_recipients)


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


def _tr(vi_text, en_text):
    lang = (get_language() or "vi").lower()
    return en_text if lang.startswith("en") else vi_text


def _team_data():
    categories = [
        {"name": "Cơ xương khớp", "slug": "co-xuong-khop"},
        {"name": "Chấn thương chỉnh hình", "slug": "chan-thuong-chinh-hinh"},
        {"name": "Thần kinh", "slug": "than-kinh"},
        {"name": "Sau tai biến", "slug": "sau-tai-bien"},
        {"name": "Sau phẫu thuật", "slug": "sau-phau-thuat"},
    ]
    doctors = [
        {
            "id": 1,
            "name": "BS.CKII Nguyễn Hoàng Minh",
            "role": "Bác sĩ Phục hồi chức năng",
            "specialty": "co-xuong-khop",
            "specialty_name": "PHCN Cơ xương khớp",
            "exp": "15+ năm",
            "education": "CKII PHCN - Đại học Y Dược TP.HCM",
            "strengths": "Đánh giá đau mạn tính, điều trị thoái hóa khớp và phục hồi vận động chuyên sâu.",
            "bio": "Ưu tiên phác đồ cá nhân hóa, theo dõi sát tiến trình và tối ưu khả năng vận động cho người bệnh.",
            "achievements": ["Top Doctor", "Clinical Mentor"],
            "image": "https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?auto=format&fit=crop&q=80&w=900",
        },
        {
            "id": 2,
            "name": "BS.CKI Trần Thu Hà",
            "role": "Bác sĩ PHCN Thần kinh",
            "specialty": "than-kinh",
            "specialty_name": "PHCN Tổn thương thần kinh",
            "exp": "12+ năm",
            "education": "CKI Thần kinh - Đại học Y Hà Nội",
            "strengths": "Phục hồi chức năng sau đột quỵ, rối loạn thăng bằng và tái học vận động.",
            "bio": "Kết hợp tập chức năng và giáo dục gia đình để cải thiện mức độ độc lập trong sinh hoạt.",
            "achievements": ["Stroke Rehab", "Neuro Care"],
            "image": "https://images.unsplash.com/photo-1594824475317-d3cb0c01f1cb?auto=format&fit=crop&q=80&w=900",
        },
        {
            "id": 3,
            "name": "BS. Lê Quốc Bảo",
            "role": "Bác sĩ Chấn thương chỉnh hình",
            "specialty": "chan-thuong-chinh-hinh",
            "specialty_name": "PHCN Chấn thương chỉnh hình",
            "exp": "10+ năm",
            "education": "BS Đa khoa - Chuyên sâu Y học thể thao",
            "strengths": "Phục hồi sau chấn thương thể thao, sau mổ dây chằng và tái hòa nhập vận động.",
            "bio": "Tập trung vào kiểm soát đau, tăng sức mạnh và phòng ngừa tái chấn thương dài hạn.",
            "achievements": ["Sports Rehab", "Return To Play"],
            "image": "https://images.unsplash.com/photo-1582750433449-648ed127bb54?auto=format&fit=crop&q=80&w=900",
        },
        {
            "id": 4,
            "name": "BS. Phạm Gia Hưng",
            "role": "Bác sĩ PHCN Sau phẫu thuật",
            "specialty": "sau-phau-thuat",
            "specialty_name": "PHCN Sau phẫu thuật",
            "exp": "11+ năm",
            "education": "Đào tạo hậu phẫu chuyên khoa ngoại",
            "strengths": "Phục hồi sau thay khớp, phẫu thuật cột sống và can thiệp chỉnh hình.",
            "bio": "Xây dựng lộ trình tập theo từng mốc hồi phục để rút ngắn thời gian trở lại sinh hoạt.",
            "achievements": ["Post-Op Care", "Fast Recovery"],
            "image": "https://images.unsplash.com/photo-1651008376811-b90baee60c1f?auto=format&fit=crop&q=80&w=900",
        },
    ]
    technicians = [
        {
            "name": "KTV Nguyễn Thanh Tâm",
            "role": "Kỹ thuật viên Vật lý trị liệu",
            "exp": "8+ năm",
            "cert": "Chứng chỉ Manual Therapy",
            "strengths": "Điều trị đau cột sống, vai gáy, phục hồi chức năng vận động.",
            "image": "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&q=80&w=700",
        },
        {
            "name": "KTV Lý Hoài Nam",
            "role": "Kỹ thuật viên Hoạt động trị liệu",
            "exp": "7+ năm",
            "cert": "Chứng chỉ OT lâm sàng",
            "strengths": "Phục hồi kỹ năng sinh hoạt hằng ngày và vận động tinh.",
            "image": "https://images.unsplash.com/photo-1622253692010-333f2da6031d?auto=format&fit=crop&q=80&w=700",
        },
        {
            "name": "KTV Trương Mỹ Linh",
            "role": "Kỹ thuật viên PHCN thần kinh",
            "exp": "6+ năm",
            "cert": "Chứng chỉ Neuro-Rehab",
            "strengths": "Tập thăng bằng, kiểm soát tư thế và cải thiện dáng đi.",
            "image": "https://images.unsplash.com/photo-1659353882074-d0e7ee52d4b1?auto=format&fit=crop&q=80&w=700",
        },
        {
            "name": "KTV Vũ Đức An",
            "role": "Kỹ thuật viên sau chấn thương",
            "exp": "9+ năm",
            "cert": "Chứng chỉ Sports Rehab",
            "strengths": "Phục hồi sau mổ dây chằng, tập sức mạnh và khả năng quay lại thể thao.",
            "image": "https://images.unsplash.com/photo-1612531385446-f7b6b8f2b4b5?auto=format&fit=crop&q=80&w=700",
        },
    ]
    return categories, doctors, technicians


def home(request):
    _, doctors, _ = _team_data()
    return render(request, "pages/home.html", {"doctors": doctors})


def about(request):
    return render(request, "pages/about.html")


def booking(request):
    booking_meta = {"appointment_date": "", "specialty": "", "service_name": ""}
    form_data = request.POST.copy() if request.method == "POST" else None
    if form_data is not None:
        booking_meta = _extract_booking_meta(form_data)
        merged_message = _merge_booking_message(form_data.get("message", ""), booking_meta)
        if merged_message:
            form_data["message"] = merged_message
        form_data["page"] = "booking"

    form = LeadForm(form_data or None, initial={"page": "booking"})
    if request.method == "POST" and form.is_valid():
        lead = form.save(commit=False)
        lead.page = "booking"
        lead.booking_date = booking_meta.get("appointment_date_obj")
        lead.booking_specialty = booking_meta.get("specialty", "")
        lead.booking_service = booking_meta.get("service_name", "")
        lead.save()
        _send_booking_notifications(lead, booking_meta)
        messages.success(request, "Đã nhận lịch khám. Chúng tôi sẽ liên hệ bạn sớm.")
        return redirect(request.path)

    return render(request, "pages/booking.html", {"lead_form": form})


def contact(request):
    saved, form = _handle_lead(request, "contact")
    if saved:
        return redirect(request.path)
    return render(request, "pages/contact.html", {"lead_form": form})


def exercise_library(request):
    can_paid = _user_can_view_paid(request.user)

    def normalize_provider_id(video_obj):
        raw = (video_obj.provider_id or "").strip()
        if not raw:
            return ""
        if "://" not in raw:
            return raw

        parsed = urlparse(raw)
        host = (parsed.netloc or "").lower().replace("www.", "")
        path = parsed.path.strip("/")

        if video_obj.provider == Video.PROVIDER_YT:
            if host == "youtu.be" and path:
                return path.split("/")[0]
            if host in {"youtube.com", "m.youtube.com"}:
                if path == "watch":
                    return parse_qs(parsed.query).get("v", [""])[0]
                if path.startswith("embed/") or path.startswith("shorts/"):
                    return path.split("/", 1)[1].split("/")[0]

        if video_obj.provider == Video.PROVIDER_VI:
            if host == "vimeo.com" and path:
                return path.split("/")[0]
            if host == "player.vimeo.com" and path.startswith("video/"):
                return path.split("/", 1)[1].split("/")[0]

        return raw

    videos = Video.objects.filter(is_active=True).select_related("category").order_by("title")
    normalized_videos = []
    for v in videos:
        provider_id = normalize_provider_id(v)
        if v.provider == Video.PROVIDER_YT and provider_id:
            embed_url = f"https://www.youtube.com/embed/{provider_id}"
            thumb_url = f"https://img.youtube.com/vi/{provider_id}/hqdefault.jpg"
            watch_url = f"https://www.youtube.com/watch?v={provider_id}"
        elif v.provider == Video.PROVIDER_VI and provider_id:
            embed_url = f"https://player.vimeo.com/video/{provider_id}"
            thumb_url = ""
            watch_url = f"https://vimeo.com/{provider_id}"
        else:
            embed_url = ""
            thumb_url = ""
            watch_url = ""

        normalized_videos.append(
            {
                "pk": v.pk,
                "title": v.title,
                "duration": v.duration,
                "category": v.category.name if v.category else "Khác",
                "provider": v.provider,
                "provider_id": provider_id,
                "embed_url": embed_url,
                "watch_url": watch_url,
                "thumb_url": thumb_url,
                "access": v.access,
                "can_watch": (v.access == Video.ACCESS_FREE) or can_paid,
            }
        )

    grouped_videos = {}
    for v in normalized_videos:
        grouped_videos.setdefault(v["category"], []).append(v)
    exercises = [{"category": key, "videos": grouped_videos[key]} for key in sorted(grouped_videos.keys())]

    return render(
        request,
        "pages/exercise_library.html",
        {
            "can_watch_paid": can_paid,
            "exercises": exercises,
        },
    )


def experts(request):
    categories, doctors, technicians = _team_data()
    return render(
        request,
        "pages/experts.html",
        {"categories": categories, "doctors": doctors, "technicians": technicians},
    )


def facilities(request):
    return render(request, "pages/facilities.html")


def faq(request):
    return render(request, "pages/faq.html")


def news_list(request, category_slug=None):
    ensure_news_categories()
    qs = NewsArticle.objects.filter(is_published=True).select_related("category", "author").order_by("-published_at", "-id")
    current_category = None
    if category_slug:
        current_category = get_object_or_404(NewsCategory, slug=category_slug)
        qs = qs.filter(category=current_category)
    page_number = request.GET.get("page")
    if qs.count() >= 2:
        featured = qs.first()
        latest_qs = qs[1:]
    else:
        featured = None
        latest_qs = qs
    page_obj = Paginator(latest_qs, 9).get_page(page_number)
    hero_description = (
        NEWS_HERO_DESCRIPTIONS.get(current_category.slug)
        if current_category
        else "Nơi chia sẻ kiến thức, kinh nghiệm và những câu chuyện truyền cảm hứng trên hành trình phục hồi sức khỏe toàn diện."
    )
    context = {
        "current_category": current_category,
        "hero_description": hero_description,
        "featured_news": featured,
        "latest_news": page_obj.object_list,
        "page_obj": page_obj,
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
    NewsArticle.objects.filter(pk=article.pk).update(view_count=F("view_count") + 1)
    article.refresh_from_db(fields=["view_count"])
    related = (
        NewsArticle.objects.filter(category=article.category, is_published=True)
        .exclude(pk=article.pk)
        .order_by("-published_at", "-id")[:3]
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


def rehab_field_detail(request, slug):
    field = REHAB_FIELD_DETAILS.get(slug)
    if not field:
        raise Http404("Không tìm thấy lĩnh vực phục hồi")
    saved, form = _handle_lead(request, f"rehab-{slug}")
    if saved:
        return redirect(request.path)
    return render(
        request,
        "pages/rehab_field_detail.html",
        {
            "field": field,
            "field_slug": slug,
            "lead_form": form,
        },
    )


def services(request):
    ensure_service_categories()
    categories = ServiceCategory.objects.all()
    services = _sorted_services(Service.objects.select_related("category").all())
    service_groups = _group_services(services)
    return render(
        request,
        "pages/services.html",
        {"categories": categories, "services": services, "service_groups": service_groups, "category": None},
    )


def services_temp(request):
    return render(request, "pages/services_temp.html")


def category_detail(request, slug):
    ensure_service_categories()
    category = get_object_or_404(ServiceCategory, slug=slug)
    services = _sorted_services(Service.objects.select_related("category").filter(category=category))
    service_groups = _group_services(services)
    categories = ServiceCategory.objects.all()
    context = {
        "category": category,
        "services": services,
        "service_groups": service_groups,
        "categories": categories,
    }
    return render(request, "pages/services.html", context)


def service_detail(request, slug):
    service = get_object_or_404(Service.objects.select_related("category"), slug=slug)
    service = _decorate_service(service)
    package_price = _parse_amount_text(service.price_text or "")
    package_duration_days = _duration_to_days(service.duration or "")
    can_checkout = package_price > 0

    related_qs = Service.objects.select_related("category").exclude(pk=service.pk)
    if service.category_id:
        related_qs = related_qs.filter(category_id=service.category_id)
    related_services = _sorted_services(related_qs)[:4]

    return render(
        request,
        "pages/service_detail.html",
        {
            "service": service,
            "related_services": related_services,
            "can_checkout": can_checkout,
            "package_duration_days": package_duration_days,
            "checkout_url": reverse("services:service_checkout", kwargs={"slug": service.slug}) if can_checkout else "",
        },
    )


def service_checkout(request, slug):
    if not request.user.is_authenticated:
        messages.error(request, "Vui lòng đăng nhập để thanh toán gói dịch vụ.")
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    service = get_object_or_404(Service.objects.select_related("category"), slug=slug)
    service = _decorate_service(service)
    try:
        package = _sync_package_from_service(service)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(service.get_absolute_url())

    latest_pending = (
        Transaction.objects.filter(user=request.user, package=package, status="pending")
        .order_by("-created_at")
        .first()
    )
    if latest_pending:
        latest_pending = _expire_transaction_if_needed(latest_pending)

    if latest_pending and latest_pending.status == "pending":
        txn = latest_pending
    else:
        txn_ref = _generate_transaction_ref()
        transfer_content = _build_transfer_content(package, service, txn_ref)
        buyer_name = (
            request.user.get_full_name().strip()
            or request.user.username
            or f"User#{request.user.pk}"
        )
        txn = Transaction.objects.create(
            user=request.user,
            package=package,
            amount=package.price,
            status="pending",
            txn_ref=txn_ref,
            raw_params={
                "service_slug": service.slug,
                "service_duration": service.display_duration,
                "transfer_content": transfer_content,
                "created_via": "service_checkout",
                "buyer_name": buyer_name,
                "buyer_username": request.user.username,
                "buyer_email": request.user.email,
            },
        )

    pending_duplicates = Transaction.objects.filter(user=request.user, package=package, status="pending").exclude(pk=txn.pk)
    for duplicate in pending_duplicates:
        _mark_transaction_failed(duplicate, reason="replaced")

    raw = dict(txn.raw_params or {})
    buyer_name = request.user.get_full_name().strip() or request.user.username
    transfer_content = str(raw.get("transfer_content") or _build_transfer_content(package, service, txn.txn_ref))
    needs_update = False
    if raw.get("transfer_content") != transfer_content:
        raw["transfer_content"] = transfer_content
        needs_update = True
    if raw.get("service_slug") != service.slug:
        raw["service_slug"] = service.slug
        needs_update = True
    if raw.get("service_duration") != service.display_duration:
        raw["service_duration"] = service.display_duration
        needs_update = True
    if raw.get("buyer_name") != buyer_name:
        raw["buyer_name"] = buyer_name
        needs_update = True
    if raw.get("buyer_username") != request.user.username:
        raw["buyer_username"] = request.user.username
        needs_update = True
    if raw.get("buyer_email") != (request.user.email or ""):
        raw["buyer_email"] = request.user.email or ""
        needs_update = True

    if needs_update:
        txn.raw_params = raw
        txn.save(update_fields=["raw_params"])

    qr_url, qr_error = _build_vietqr_url(package.price, transfer_content)

    context = {
        "service": service,
        "package": package,
        "transaction": txn,
        "buyer_name": request.user.get_full_name().strip() or request.user.username,
        "buyer_username": request.user.username,
        "buyer_email": request.user.email or "Chưa cập nhật",
        "transfer_content": transfer_content,
        "qr_url": qr_url,
        "qr_error": qr_error,
        "payment_timeout_seconds": PAYMENT_TIMEOUT_SECONDS,
        "deadline_iso": _transaction_deadline(txn).isoformat(),
        "status_url": reverse("services:service_checkout_status", kwargs={"txn_ref": txn.txn_ref}),
    }
    return render(request, "pages/service_checkout.html", context)


def service_checkout_status(request, txn_ref):
    if not request.user.is_authenticated:
        return JsonResponse({"status": "unauthenticated"}, status=401)

    txn = get_object_or_404(
        Transaction.objects.select_related("package"),
        txn_ref=txn_ref,
        user=request.user,
    )
    txn = _expire_transaction_if_needed(txn)
    remaining_seconds = _transaction_remaining_seconds(txn) if txn.status == "pending" else 0

    payload = {
        "status": txn.status,
        "txn_ref": txn.txn_ref,
        "remaining_seconds": remaining_seconds,
        "amount": str(txn.amount),
    }
    if txn.status == "success":
        payload["redirect_url"] = "/auth/profile/"
        payload["message"] = "Thanh toán thành công. Gói đã được kích hoạt."
    elif txn.status == "failed":
        payload["message"] = "Thanh toán thất bại hoặc đã quá hạn 3 phút."

    return JsonResponse(payload)


def speech_therapy(request):
    return render(request, "pages/speech_therapy.html")


def visit_guide(request):
    return render(request, "pages/visit_guide.html")


def buy_package(request, slug):
    package = Package.objects.filter(slug=slug, is_active=True).first()
    if not package:
        messages.error(request, "Gói tập chưa sẵn sàng, vui lòng chọn dịch vụ khác.")
        return redirect('/services/')
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
def qr_payment_webhook(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method_not_allowed"}, status=405)

    webhook_secret = str(getattr(settings, "QR_WEBHOOK_SECRET", "") or "").strip()
    if webhook_secret and request.headers.get("X-QR-SECRET", "") != webhook_secret:
        return JsonResponse({"ok": False, "error": "invalid_secret"}, status=403)

    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "payload_must_be_object"}, status=400)

    txn_ref = _extract_txn_ref_from_payload(payload)
    if not txn_ref:
        return JsonResponse({"ok": False, "error": "missing_txn_ref"}, status=400)

    txn = Transaction.objects.select_related("package", "user").filter(txn_ref=txn_ref).first()
    if not txn:
        return JsonResponse({"ok": False, "error": "transaction_not_found"}, status=404)

    txn = _expire_transaction_if_needed(txn)
    if txn.status == "failed":
        return JsonResponse({"ok": False, "status": "failed", "error": "transaction_expired"}, status=409)
    if txn.status == "success":
        return JsonResponse({"ok": True, "status": "success", "txn_ref": txn.txn_ref})

    provider_status = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("event")
        or ""
    ).strip().lower()
    if provider_status in {"failed", "error", "cancel", "cancelled", "timeout"}:
        _mark_transaction_failed(txn, reason=provider_status or "provider_failed")
        return JsonResponse({"ok": False, "status": "failed", "txn_ref": txn.txn_ref}, status=400)
    if provider_status in {"pending", "processing", "waiting"}:
        return JsonResponse({"ok": True, "status": "pending", "txn_ref": txn.txn_ref})

    paid_amount = _parse_payload_amount(payload)
    if paid_amount is not None and paid_amount < txn.amount:
        _mark_transaction_failed(txn, reason="amount_mismatch")
        return JsonResponse(
            {
                "ok": False,
                "error": "amount_mismatch",
                "txn_ref": txn.txn_ref,
                "expected": str(txn.amount),
                "received": str(paid_amount),
            },
            status=400,
        )

    raw = dict(txn.raw_params or {})
    raw["webhook_payload"] = payload
    raw["paid_amount"] = str(paid_amount) if paid_amount is not None else ""
    raw["paid_at"] = timezone.now().isoformat()
    txn.status = "success"
    txn.raw_params = raw
    txn.save(update_fields=["status", "raw_params"])

    purchase = _activate_purchase_for_transaction(txn)
    return JsonResponse(
        {
            "ok": True,
            "status": "success",
            "txn_ref": txn.txn_ref,
            "purchase_id": purchase.pk,
        }
    )


@csrf_exempt
def login_view(request):
    """
    Simple username/password login using Django's AuthenticationForm.
    Supports ?next= redirect.
    """
    def _resolve_next(default_target):
        target = (request.POST.get("next") or request.GET.get("next") or "").strip()
        if not target.startswith("/"):
            return default_target
        if target.startswith("//"):
            return default_target
        return target

    def _user_next():
        target = _resolve_next("/")
        if target.startswith("/hansviet_admin/"):
            return "/"
        return target

    def _admin_next():
        target = _resolve_next(settings.LOGIN_REDIRECT_URL)
        if not target.startswith("/hansviet_admin/"):
            return settings.LOGIN_REDIRECT_URL
        return target

    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return redirect(_user_next())

    admin_login_url = getattr(settings, "ADMIN_LOGIN_URL", "/hansviet_admin/login/")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            if user.is_staff or user.is_superuser:
                messages.error(request, "Tai khoan admin vui long dang nhap o trang admin.")
                return redirect(f"{admin_login_url}?next={_admin_next()}")
            login(request, user)

            return redirect(_user_next())
        else:
            messages.error(request, "Tên đăng nhập hoặc mật khẩu không đúng.")

    return render(request, "auth/login.html", {"form": form, "next": _user_next()})


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


def profile_view(request):
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next=/auth/profile/")

    purchases = (
        Purchase.objects.select_related("package")
        .filter(user=request.user)
        .order_by("-started_at", "-id")
    )
    now = timezone.now()
    active_purchases = []
    purchase_history = []
    for item in purchases:
        is_active_now = item.status == "active" and item.expires_at > now
        item.is_active_now = is_active_now
        if is_active_now:
            active_purchases.append(item)
        else:
            purchase_history.append(item)

    context = {
        "active_purchases": active_purchases,
        "purchase_history": purchase_history,
        "purchase_count": purchases.count(),
    }
    return render(request, "auth/profile.html", context)


def care_management_view(request):
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next=/auth/care-management/")

    user = request.user
    patient_profile, _ = PatientProfile.objects.get_or_create(user=user)
    exercise_profile, _ = ExerciseProfile.objects.get_or_create(user=user)

    action = request.POST.get("action")
    if request.method == "POST":
        if action == "update_medical":
            patient_profile.condition = (request.POST.get("condition") or "").strip()
            patient_profile.notes = (request.POST.get("medical_notes") or "").strip()
            patient_profile.save()
            messages.success(
                request,
                _tr("Đã cập nhật hồ sơ bệnh án đơn giản.", "Simple medical profile updated."),
            )
            return redirect("/auth/care-management/")

        if action == "add_progress":
            summary = (request.POST.get("summary") or "").strip()
            score_raw = (request.POST.get("score") or "").strip()
            if summary:
                score = int(score_raw) if score_raw.isdigit() else None
                ProgressNote.objects.create(profile=patient_profile, summary=summary, score=score)
                messages.success(request, _tr("Đã thêm ghi chú tiến triển.", "Progress note added."))
            else:
                messages.error(
                    request,
                    _tr("Nội dung tiến triển không được để trống.", "Progress summary cannot be empty."),
                )
            return redirect("/auth/care-management/")

        if action == "add_schedule":
            title = (request.POST.get("title") or "").strip()
            start_at = request.POST.get("start_at")
            end_at = request.POST.get("end_at")
            is_zoom = request.POST.get("is_zoom") == "on"
            if title and start_at and end_at:
                try:
                    start_dt = datetime.fromisoformat(start_at)
                    end_dt = datetime.fromisoformat(end_at)
                except ValueError:
                    messages.error(request, _tr("Định dạng ngày giờ không hợp lệ.", "Invalid date/time format."))
                    return redirect("/auth/care-management/")
                SessionSchedule.objects.create(
                    user=user,
                    title=title,
                    start_at=start_dt,
                    end_at=end_dt,
                    is_zoom=is_zoom,
                    zoom_join_url=(request.POST.get("zoom_join_url") or "").strip(),
                    zoom_meeting_id=(request.POST.get("zoom_meeting_id") or "").strip(),
                )
                messages.success(request, _tr("Đã thêm lịch tập.", "Schedule added."))
            else:
                messages.error(
                    request,
                    _tr("Vui lòng nhập đủ tiêu đề và thời gian lịch tập.", "Please provide title and schedule time."),
                )
            return redirect("/auth/care-management/")

        if action == "update_exercise_profile":
            exercise_profile.goals = (request.POST.get("goals") or "").strip()
            exercise_profile.contraindications = (request.POST.get("contraindications") or "").strip()
            exercise_profile.current_level = (request.POST.get("current_level") or "").strip()
            exercise_profile.save()
            messages.success(request, _tr("Đã cập nhật hồ sơ bài tập.", "Exercise profile updated."))
            return redirect("/auth/care-management/")

        if action == "add_exercise_log":
            exercise_name = (request.POST.get("exercise_name") or "").strip()
            if exercise_name:
                duration_raw = (request.POST.get("duration_minutes") or "0").strip()
                pain_raw = (request.POST.get("pain_score") or "0").strip()
                ExerciseLog.objects.create(
                    user=user,
                    exercise_name=exercise_name,
                    category=(request.POST.get("exercise_category") or "").strip(),
                    duration_minutes=int(duration_raw) if duration_raw.isdigit() else 0,
                    pain_score=int(pain_raw) if pain_raw.isdigit() else 0,
                    notes=(request.POST.get("exercise_notes") or "").strip(),
                )
                messages.success(request, _tr("Đã lưu lịch sử bài tập.", "Exercise log saved."))
            else:
                messages.error(request, _tr("Tên bài tập không được để trống.", "Exercise name cannot be empty."))
            return redirect("/auth/care-management/")

    schedules = SessionSchedule.objects.filter(user=user).order_by("-start_at")
    progress_notes = ProgressNote.objects.filter(profile=patient_profile).order_by("-recorded_at")
    exercise_logs = ExerciseLog.objects.filter(user=user).order_by("-trained_at")
    context = {
        "patient_profile": patient_profile,
        "exercise_profile": exercise_profile,
        "schedules": schedules,
        "progress_notes": progress_notes,
        "exercise_logs": exercise_logs,
    }
    return render(request, "auth/care_management.html", context)


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
