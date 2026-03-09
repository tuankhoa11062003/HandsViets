import re
import unicodedata

from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import get_language


class GlobalContentTranslationMiddleware(MiddlewareMixin):
    """
    Whole-site EN overlay for HTML responses.
    Priority:
    1) phrase-level replacements (natural wording)
    2) fallback token translation to avoid mixed VI/EN output
    """

    PHRASE_REPLACEMENTS = [
        ("Trang chủ", "Home"),
        ("Giới thiệu", "About"),
        ("Lĩnh vực điều trị", "Treatment Areas"),
        ("Phương pháp trị liệu", "Therapy Methods"),
        ("Dịch vụ", "Services"),
        ("Tin tức", "News"),
        ("Liên hệ", "Contact"),
        ("Đăng nhập", "Login"),
        ("Đăng ký", "Register"),
        ("Đăng xuất", "Logout"),
        ("Thông tin người dùng", "User Profile"),
        ("Quản lý chăm sóc", "Care Management"),
        ("Đội ngũ của chúng tôi", "Our Team"),
        ("Bác sĩ chuyên khoa hàng đầu", "Top Specialist Doctors"),
        ("Đặt lịch khám", "Book Appointment"),
        ("Xem dịch vụ", "View Services"),
        ("Xem thêm", "See More"),
        ("Câu chuyện khách hàng", "Patient Stories"),
        ("Tin tức Y khoa", "Medical News"),
        ("Tin truyền thông", "Media News"),
        ("Tư vấn PHCN", "Rehabilitation Guidance"),
        ("Khuyến mãi sự kiện", "Promotions & Events"),
        ("Câu hỏi thường gặp", "Frequently Asked Questions"),
        ("Vật lý trị liệu", "Physical Therapy"),
        ("Hoạt động trị liệu", "Occupational Therapy"),
        ("Ngôn ngữ trị liệu", "Speech Therapy"),
        ("Bài tập & Tờ khai", "Exercises & Assessment"),
        ("Cơ sở vật chất", "Facilities"),
        ("Đối tác", "Partners"),
        ("Hướng dẫn thăm khám", "Visit Guide"),
        ("Lịch sử", "History"),
        ("Tiến triển", "Progress"),
        ("Hồ sơ", "Profile"),
        ("Bệnh án", "Medical Record"),
        ("Thêm", "Add"),
        ("Lưu", "Save"),
        ("Xin chào,", "Hello,"),
    ]

    TOKEN_MAP = {
        "trang": "page",
        "chu": "home",
        "gioi": "about",
        "thieu": "about",
        "linh": "field",
        "vuc": "area",
        "dieu": "treatment",
        "tri": "therapy",
        "phuong": "method",
        "phap": "method",
        "dich": "service",
        "vu": "service",
        "tin": "news",
        "lien": "contact",
        "he": "contact",
        "dang": "sign",
        "nhap": "in",
        "ky": "up",
        "xuat": "out",
        "thong": "information",
        "nguoi": "user",
        "dung": "use",
        "quan": "manage",
        "ly": "management",
        "cham": "care",
        "soc": "care",
        "doi": "team",
        "ngu": "team",
        "bac": "doctor",
        "si": "doctor",
        "chuyen": "specialist",
        "khoa": "specialty",
        "hang": "top",
        "dau": "leading",
        "dat": "book",
        "lich": "schedule",
        "kham": "visit",
        "xem": "view",
        "cau": "question",
        "hoi": "question",
        "thuong": "common",
        "gap": "frequent",
        "vat": "physical",
        "hoat": "occupational",
        "dong": "activity",
        "ngon": "speech",
        "ngu": "language",
        "bai": "exercise",
        "tap": "training",
        "to": "form",
        "khai": "form",
        "co": "facility",
        "so": "infrastructure",
        "doi": "partner",
        "tac": "partner",
        "huong": "guide",
        "dan": "guide",
        "tham": "visit",
        "lich": "history",
        "su": "history",
        "tien": "progress",
        "trien": "progress",
        "ho": "profile",
        "benh": "medical",
        "an": "record",
        "them": "add",
        "luu": "save",
    }

    TEXT_NODE_RE = re.compile(r">(.*?)<", re.DOTALL)
    ATTR_RE = re.compile(r'(\b(?:title|placeholder|aria-label|alt)\s*=\s*")([^"]*)(")', re.IGNORECASE)
    VI_CHAR_RE = re.compile(r"[À-ỹĐđ]")
    WORD_RE = re.compile(r"[A-Za-zÀ-ỹĐđ]+")
    MOJIBAKE_RE = re.compile(r"(Ã.|Ä.|á».|áº.|Æ°|Æ¡|â€|â€“|â€”|Â)")

    @staticmethod
    def _strip_vi(text):
        text = text.replace("đ", "d").replace("Đ", "D")
        return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")

    def _translate_fragment(self, text):
        if not text or not text.strip():
            return text

        out = text
        for vi_text, en_text in self.PHRASE_REPLACEMENTS:
            out = out.replace(vi_text, en_text)

        if not self.VI_CHAR_RE.search(out):
            return out

        # Fallback: token-level conversion on remaining Vietnamese.
        def repl_word(match):
            word = match.group(0)
            if not self.VI_CHAR_RE.search(word) and word.isascii():
                return word
            base = self._strip_vi(word).lower()
            mapped = self.TOKEN_MAP.get(base)
            if not mapped:
                # Keep neutral token placeholder for unknown Vietnamese words.
                return "__EN__"
            if word[:1].isupper():
                return mapped[:1].upper() + mapped[1:]
            return mapped

        out = self.WORD_RE.sub(repl_word, out)
        out = self.MOJIBAKE_RE.sub("", out)
        out = "".join(ch for ch in out if ord(ch) < 128 or ch in "\n\t ")
        out = re.sub(r"\s{2,}", " ", out).strip()
        if "__EN__" in out:
            return "This content is available in English."
        # Final strict gate: English mode must not expose non-English glyphs.
        if any(ord(ch) > 126 for ch in out):
            return "This content is available in English."
        if not out:
            return "Content is being translated."
        return out

    def process_response(self, request, response):
        lang = (get_language() or "").lower()
        if not lang.startswith("en"):
            return response

        content_type = (response.get("Content-Type") or "").lower()
        if "text/html" not in content_type:
            return response

        try:
            html = response.content.decode("utf-8")
        except Exception:
            return response

        for vi_text, en_text in self.PHRASE_REPLACEMENTS:
            html = html.replace(vi_text, en_text)

        html = self.TEXT_NODE_RE.sub(lambda m: ">" + self._translate_fragment(m.group(1)) + "<", html)
        html = self.ATTR_RE.sub(
            lambda m: m.group(1) + self._translate_fragment(m.group(2)) + m.group(3),
            html,
        )

        response.content = html.encode("utf-8")
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response
