import imghdr
import unicodedata
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from hansviet_admin.models import NewsArticle, NewsCategory
from hansviet_admin.services.news_content import ensure_detailed_content, ensure_summary
from hansviet_admin.services.perplexity_news import unique_article_slug
from hansviet_admin.services.rss_news import fetch_rss_items


DEFAULT_FEEDS = [
    ("https://vnexpress.net/rss/suc-khoe.rss", "VnExpress"),
    ("https://tuoitre.vn/rss/suc-khoe.rss", "Tuoi Tre"),
    ("https://thanhnien.vn/rss/suc-khoe.rss", "Thanh Nien"),
    ("https://www.medicalnewstoday.com/articles.rss", "Medical News Today"),
    ("https://www.who.int/news-room/rss-feeds", "WHO"),
]

CATEGORY_SLUGS = {
    "story": "cau-chuyen-khach-hang",
    "event": "khuyen-mai-su-kien",
    "media": "tin-truyen-thong",
    "medical": "tin-tuc-y-khoa",
    "consult": "tu-van-phcn",
}


def _normalize_text(text: str) -> str:
    base = (text or "").lower()
    base = "".join(ch for ch in unicodedata.normalize("NFD", base) if unicodedata.category(ch) != "Mn")
    return base.replace("đ", "d").replace("Đ", "D")


def _topic_category_slug(title: str, summary: str, source_name: str) -> str | None:
    text = _normalize_text(f"{title} {summary} {source_name}")
    if any(k in text for k in ["khuyen mai", "uu dai", "giam gia", "su kien", "workshop", "hoi thao"]):
        return CATEGORY_SLUGS["event"]
    if any(k in text for k in ["truyen thong", "bao chi", "phong su", "dua tin", "media"]):
        return CATEGORY_SLUGS["media"]
    if any(k in text for k in ["cau chuyen", "hanh trinh", "khach hang", "benh nhan chia se", "case study"]):
        return CATEGORY_SLUGS["story"]
    if any(
        k in text
        for k in [
            "phuc hoi chuc nang",
            "phcn",
            "vat ly tri lieu",
            "rehab",
            "van dong tri lieu",
            "chan thuong chinh hinh",
            "dau lung",
            "cot song",
            "xuong khop",
            "dot quy",
            "sau mo",
        ]
    ):
        return CATEGORY_SLUGS["consult"]
    return None


class Command(BaseCommand):
    help = "Sync news from trusted RSS feeds into NewsArticle."

    def add_arguments(self, parser):
        parser.add_argument("--max-items", type=int, default=3, help="Max items per feed.")
        parser.add_argument("--publish", action="store_true", help="Publish immediately.")
        parser.add_argument("--feed", action="append", dest="feeds", help="Custom RSS feed URL.")
        parser.add_argument(
            "--balanced",
            action="store_true",
            help="When topic is unclear, spread items across categories instead of defaulting to medical news.",
        )

    def handle(self, *args, **options):
        max_items = max(1, int(options["max_items"]))
        auto_publish = bool(options.get("publish"))
        balanced = bool(options.get("balanced"))
        created_count = 0
        skipped_count = 0

        custom_feeds = options.get("feeds") or []
        feed_rows = list(DEFAULT_FEEDS)
        if custom_feeds:
            feed_rows = [(u.strip(), "RSS Custom") for u in custom_feeds if u.strip()]

        categories_by_slug = {c.slug: c for c in NewsCategory.objects.all()}
        if CATEGORY_SLUGS["medical"] not in categories_by_slug:
            self.stdout.write(self.style.ERROR("Missing required category 'tin-tuc-y-khoa'."))
            return

        bucket_order = [
            CATEGORY_SLUGS["consult"],
            CATEGORY_SLUGS["medical"],
            CATEGORY_SLUGS["media"],
            CATEGORY_SLUGS["story"],
            CATEGORY_SLUGS["event"],
        ]
        created_buckets = {slug: 0 for slug in bucket_order}

        def _download_image_file(url: str, title: str) -> ContentFile | None:
            if not url:
                return None
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0 (HandsViet RSS Bot)"})
                with urlopen(req, timeout=45) as resp:
                    data = resp.read()
                if not data:
                    return None
                kind = imghdr.what(None, h=data) or "jpg"
                if kind == "jpeg":
                    kind = "jpg"
                safe_title = "".join(ch if ch.isalnum() else "-" for ch in (title or "rss-news")).strip("-").lower()
                safe_title = safe_title[:50] or "rss-news"
                name = f"{safe_title}-{timezone.now().strftime('%Y%m%d%H%M%S')}.{kind}"
                cf = ContentFile(data)
                cf.name = name
                return cf
            except Exception:
                return None

        for feed_url, source_name in feed_rows:
            self.stdout.write(f"Syncing RSS: {feed_url}")
            try:
                items = fetch_rss_items(feed_url, source_name=source_name, max_items=max_items)
            except Exception as ex:
                self.stdout.write(self.style.ERROR(f"RSS error '{feed_url}': {ex}"))
                continue

            for item in items:
                if NewsArticle.objects.filter(source_url=item.source_url).exists():
                    skipped_count += 1
                    continue
                if NewsArticle.objects.filter(title__iexact=item.title).exists():
                    skipped_count += 1
                    continue

                topic_slug = _topic_category_slug(item.title, item.summary, item.source_name)
                if topic_slug:
                    chosen_slug = topic_slug
                elif balanced:
                    chosen_slug = min(bucket_order, key=lambda slug: created_buckets.get(slug, 0))
                else:
                    chosen_slug = CATEGORY_SLUGS["medical"]

                target_category = categories_by_slug.get(chosen_slug) or categories_by_slug[CATEGORY_SLUGS["medical"]]
                slug_value = unique_article_slug(item.title, exists_fn=lambda s: NewsArticle.objects.filter(slug=s).exists())

                article = NewsArticle.objects.create(
                    category=target_category,
                    title=item.title,
                    slug=slug_value,
                    summary=ensure_summary(item.title, item.summary),
                    content=ensure_detailed_content(
                        title=item.title,
                        summary=item.summary,
                        content=item.content,
                        source_url=item.source_url,
                        source_name=item.source_name,
                        category_name=target_category.name,
                        image_url=item.image_url,
                    ),
                    is_published=auto_publish,
                    source_url=item.source_url,
                    source_name=item.source_name,
                    ai_source="rss",
                    is_auto_generated=True,
                    needs_review=not auto_publish,
                )
                if item.published_at:
                    article.published_at = item.published_at
                    article.save(update_fields=["published_at"])

                if item.image_url:
                    image_file = _download_image_file(item.image_url, item.title)
                    if image_file:
                        article.thumbnail.save(image_file.name, image_file, save=True)

                created_buckets[chosen_slug] = created_buckets.get(chosen_slug, 0) + 1
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done RSS sync. created={created_count}, skipped={skipped_count}, "
                f"mode={'publish' if auto_publish else 'draft'}, balanced={balanced}, at={timezone.now()}"
            )
        )

