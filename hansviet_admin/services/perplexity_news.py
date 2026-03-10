import json
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils.text import slugify


@dataclass
class NewsItem:
    title: str
    summary: str
    content: str
    source_url: str
    source_name: str
    image_url: str = ""
    published_at: datetime | None = None


SYSTEM_PROMPT = (
    "Bạn là biên tập viên tin y tế tiếng Việt. "
    "BẮT BUỘC trả về tiếng Việt tự nhiên, không dùng tiếng Anh, không markdown. "
    "Mỗi bài phải chi tiết, có chiều sâu, tránh viết chung chung. "
    "summary dài từ 80 đến 160 từ. "
    "content dài từ 900 đến 1600 từ, dùng HTML đơn giản (h2, h3, p, ul, li). "
    "Nội dung phải có các phần: bối cảnh, số liệu/chứng cứ, tác động lâm sàng, khuyến nghị cho người dân Việt Nam. "
    "Nếu có ảnh phù hợp thì điền image_url là URL ảnh minh họa công khai. "
    "Chỉ trả về JSON UTF-8 theo schema: "
    "{\"items\":[{\"title\":\"...\",\"summary\":\"...\",\"content\":\"...\","
    "\"source_url\":\"https://...\",\"source_name\":\"...\",\"image_url\":\"https://...\","
    "\"published_at\":\"YYYY-MM-DDTHH:MM:SSZ\"}]}."
)


def _build_user_prompt(category_name: str, max_items: int) -> str:
    return (
        f"Hãy lấy tối đa {max_items} tin mới nhất phù hợp chuyên mục '{category_name}' cho độc giả Việt Nam. "
        "Mỗi tin cần đúng trọng tâm, có nguồn trích dẫn đáng tin cậy. "
        "Bắt buộc tiếng Việt tự nhiên. "
        "summary cần nêu rõ điểm chính và ý nghĩa thực tiễn. "
        "content cần phân tích sâu, có giá trị ứng dụng cho bệnh nhân và gia đình."
    )


def _parse_json_from_text(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def _has_vietnamese_tone(text: str) -> bool:
    return bool(
        re.search(
            r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệóòỏõọốồổỗộớờởỡợúùủũụứừửữựíìỉĩịýỳỷỹỵ]",
            text.lower(),
        )
    )


def _ensure_length(item: dict) -> dict:
    summary = (item.get("summary") or "").strip()
    content = (item.get("content") or "").strip()
    if len(summary) < 180 and content:
        item["summary"] = (content[:380].rsplit(" ", 1)[0] + "...").strip()
    if len(content) < 1500:
        filler = (
            "<h2>Khuyến nghị thực hành</h2>"
            "<p>Người dân nên theo dõi thông tin từ cơ quan y tế chính thống, "
            "tuân thủ hướng dẫn của bác sĩ và không tự ý điều trị theo nguồn chưa kiểm chứng.</p>"
            "<ul>"
            "<li>Khám sớm khi có dấu hiệu bất thường.</li>"
            "<li>Duy trì lối sống lành mạnh, vận động phù hợp.</li>"
            "<li>Tái khám định kỳ theo chỉ định chuyên môn.</li>"
            "</ul>"
        )
        item["content"] = (content + "\n\n" + filler).strip()
    return item


def _translate_item_to_vietnamese(item: dict) -> dict:
    translate_prompt = (
        "Dịch toàn bộ object sau sang tiếng Việt tự nhiên, giữ nguyên cấu trúc JSON, "
        "không thêm giải thích. Object: " + json.dumps(item, ensure_ascii=False)
    )
    response = _post_chat(
        [
            {"role": "system", "content": "Bạn là biên tập viên tiếng Việt. Chỉ trả về JSON hợp lệ."},
            {"role": "user", "content": translate_prompt},
        ]
    )
    content = response["choices"][0]["message"]["content"]
    return _parse_json_from_text(content)


def _post_chat(messages: list[dict]) -> dict:
    if not settings.PPLX_API_KEY:
        raise RuntimeError("Missing PPLX_API_KEY in environment/settings.")

    payload = {
        "model": settings.PPLX_MODEL,
        "temperature": 0.2,
        "messages": messages,
    }
    base = settings.PPLX_BASE_URL.rstrip("/") + "/"
    candidate_paths = [
        "v1/chat/completions",
        "chat/completions",
        "api/v1/chat/completions",
        "openai/v1/chat/completions",
    ]
    last_error = None
    for path in candidate_paths:
        endpoint = urljoin(base, path)
        req = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.PPLX_API_KEY}",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=settings.PPLX_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    preview = raw[:200].replace("\n", " ")
                    last_error = RuntimeError(f"{endpoint} returned non-JSON response: {preview}")
                    continue
        except HTTPError as ex:
            last_error = RuntimeError(f"{endpoint} HTTPError {ex.code}: {ex.reason}")
        except URLError as ex:
            last_error = RuntimeError(f"{endpoint} URLError: {ex.reason}")

    if last_error:
        raise last_error
    raise RuntimeError("Unable to reach API endpoint.")


def fetch_category_news(category_name: str, max_items: int = 5) -> list[NewsItem]:
    response = _post_chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(category_name, max_items)},
        ]
    )
    content = response["choices"][0]["message"]["content"]
    parsed = _parse_json_from_text(content)

    items: list[NewsItem] = []
    for row in parsed.get("items", []):
        joined = " ".join([str(row.get("title", "")), str(row.get("summary", "")), str(row.get("content", ""))])
        if not _has_vietnamese_tone(joined):
            try:
                row = _translate_item_to_vietnamese(row)
            except Exception:
                pass
        row = _ensure_length(row)
        title = (row.get("title") or "").strip()
        summary = (row.get("summary") or "").strip()
        body = (row.get("content") or "").strip()
        source_url = (row.get("source_url") or "").strip()
        source_name = (row.get("source_name") or "").strip()
        image_url = (row.get("image_url") or "").strip()
        published_at_raw = (row.get("published_at") or "").strip()
        published_at = None
        if published_at_raw:
            try:
                published_at = datetime.fromisoformat(published_at_raw.replace("Z", "+00:00"))
            except ValueError:
                published_at = None
        if not title:
            continue
        items.append(
            NewsItem(
                title=title,
                summary=summary,
                content=body,
                source_url=source_url,
                source_name=source_name,
                image_url=image_url,
                published_at=published_at,
            )
        )
    return items


def unique_article_slug(title: str, exists_fn) -> str:
    base = slugify(title) or "tin-tuc-moi"
    slug = base
    i = 2
    while exists_fn(slug):
        slug = f"{base}-{i}"
        i += 1
    return slug

