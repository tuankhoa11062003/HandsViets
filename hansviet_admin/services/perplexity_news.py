import json
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils.text import slugify
from hansviet_admin.services.news_content import ensure_detailed_content, ensure_summary


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
    "Ban la bien tap vien tin y te cho doc gia Viet Nam. "
    "Bat buoc tra ve tieng Viet tu nhien, khong markdown. "
    "Moi bai can co tom tat ro rang va noi dung chi tiet, co gia tri thuc hanh. "
    "summary tu 80 den 160 tu. "
    "content tu 900 den 1600 tu, dung HTML don gian (h2, h3, p, ul, li). "
    "Tra ve JSON theo schema: "
    "{\"items\":[{\"title\":\"...\",\"summary\":\"...\",\"content\":\"...\","
    "\"source_url\":\"https://...\",\"source_name\":\"...\",\"image_url\":\"https://...\","
    "\"published_at\":\"YYYY-MM-DDTHH:MM:SSZ\"}]}"
)


def _build_user_prompt(category_name: str, max_items: int) -> str:
    return (
        f"Hay lay toi da {max_items} tin moi nhat phu hop chuyen muc '{category_name}' cho doc gia Viet Nam. "
        "Noi dung phai dung trong tam, co nguon tham khao ro rang. "
        "Summary neu ro diem chinh. Content can phan tich sau va co khuyen nghi thuc hanh."
    )


def _parse_json_from_text(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def _has_vietnamese_tone(text: str) -> bool:
    lowered = f" {text.lower()} "
    markers = [
        " va ",
        " cua ",
        " benh ",
        " dieu tri ",
        " phuc hoi ",
        " suc khoe ",
        " bệnh ",
        " điều trị ",
        " phục hồi ",
        " sức khỏe ",
    ]
    return any(marker in lowered for marker in markers)


def _ensure_length(item: dict) -> dict:
    title = (item.get("title") or "").strip()
    source_url = (item.get("source_url") or "").strip()
    source_name = (item.get("source_name") or "").strip()
    image_url = (item.get("image_url") or "").strip()

    summary = ensure_summary(title=title, summary=(item.get("summary") or ""), min_len=280, min_words=55)
    content = ensure_detailed_content(
        title=title,
        summary=summary,
        content=(item.get("content") or ""),
        source_url=source_url,
        source_name=source_name,
        image_url=image_url,
        min_len=2200,
        min_words=360,
    )

    item["summary"] = summary
    item["content"] = content
    return item


def _translate_item_to_vietnamese(item: dict) -> dict:
    translate_prompt = (
        "Translate this object to natural Vietnamese, keep exact JSON structure and return JSON only. Object: "
        + json.dumps(item, ensure_ascii=False)
    )
    response = _post_chat(
        [
            {"role": "system", "content": "You are a Vietnamese medical editor. Return valid JSON only."},
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



