import uuid
from datetime import timedelta
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import get_language
from django.http import Http404, HttpResponse
from django.db.models import F
from django.core.paginator import Paginator

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
        NewsCategory.objects.get_or_create(slug=slug, defaults={"name": name})


def ensure_service_categories():
    for index, (name, slug) in enumerate(DEFAULT_SERVICE_CATEGORIES):
        ServiceCategory.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "order": index},
        )


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
    services = Service.objects.select_related("category").all()
    return render(
        request,
        "pages/services.html",
        {"categories": categories, "services": services, "category": None},
    )


def services_temp(request):
    return render(request, "pages/services_temp.html")


def category_detail(request, slug):
    ensure_service_categories()
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
def login_view(request):
    """
    Simple username/password login using Django's AuthenticationForm.
    Supports ?next= redirect.
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


def profile_view(request):
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next=/auth/profile/")
    return render(request, "auth/profile.html")


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
