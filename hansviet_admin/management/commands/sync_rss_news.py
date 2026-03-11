import imghdr
import unicodedata
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from hansviet_admin.models import NewsArticle, NewsCategory
from hansviet_admin.services.news_content import ensure_detailed_content, ensure_summary
from hansviet_admin.services.perplexity_news import unique_article_slug
from hansviet_admin.services.rss_news import fetch_rss_items


DEFAULT_NEWS_CATEGORIES = [
    ("Tin tức Y khoa", "tin-tuc-y-khoa"),
    ("Tư vấn PHCN", "tu-van-phcn"),
    ("Tin truyền thông", "tin-truyen-thong"),
    ("Khuyến mãi sự kiện", "khuyen-mai-su-kien"),
    ("Câu chuyện khách hàng", "cau-chuyen-khach-hang"),
]

DEFAULT_FEEDS = [
    ("https://vnexpress.net/rss/suc-khoe.rss", "VnExpress"),
    ("https://tuoitre.vn/rss/suc-khoe.rss", "Tuoi Tre"),
    ("https://thanhnien.vn/rss/suc-khoe.rss", "Thanh Nien"),
]

CATEGORY_SLUGS = {
    "story": "cau-chuyen-khach-hang",
    "event": "khuyen-mai-su-kien",
    "media": "tin-truyen-thong",
    "medical": "tin-tuc-y-khoa",
    "consult": "tu-van-phcn",
}

KEYWORDS_BY_CATEGORY = {
    CATEGORY_SLUGS["event"]: [
        ("khuyen mai", 4),
        ("uu dai", 4),
        ("mien phi", 3),
        ("giam gia", 3),
        ("su kien", 3),
        ("workshop", 3),
        ("hoi thao", 3),
        ("dang ky", 2),
        ("chuong trinh", 2),
    ],
    CATEGORY_SLUGS["media"]: [
        ("truyen thong", 4),
        ("bao chi", 3),
        ("thong cao", 3),
        ("phong su", 3),
        ("dua tin", 2),
        ("phat song", 2),
        ("truyen hinh", 2),
        ("media", 2),
    ],
    CATEGORY_SLUGS["story"]: [
        ("cau chuyen", 4),
        ("hanh trinh", 3),
        ("khach hang", 3),
        ("benh nhan chia se", 4),
        ("chia se", 2),
        ("vuot qua", 2),
        ("case study", 3),
    ],
    CATEGORY_SLUGS["consult"]: [
        ("phuc hoi chuc nang", 4),
        ("phcn", 4),
        ("vat ly tri lieu", 4),
        ("hoat dong tri lieu", 4),
        ("ngon ngu tri lieu", 4),
        ("rehab", 3),
        ("huong dan", 2),
        ("tu van", 2),
        ("cham soc tai nha", 2),
        ("dau lung", 2),
        ("xuong khop", 2),
        ("dot quy", 2),
        ("sau mo", 2),
    ],
    CATEGORY_SLUGS["medical"]: [
        ("y te", 2),
        ("suc khoe", 2),
        ("benh", 2),
        ("trieu chung", 2),
        ("dieu tri", 2),
        ("nghien cuu", 2),
        ("vaccine", 2),
        ("virus", 2),
        ("kham", 1),
        ("bac si", 1),
        ("xet nghiem", 1),
    ],
}


def _normalize_text(text: str) -> str:
    base = (text or "").lower()
    base = "".join(ch for ch in unicodedata.normalize("NFD", base) if unicodedata.category(ch) != "Mn")
    return base.replace("đ", "d").replace("Đ", "d")


def _topic_scores(title: str, summary: str, source_name: str) -> dict[str, int]:
    text = _normalize_text(f"{title} {summary} {source_name}")
    scores = {slug: 0 for slug in KEYWORDS_BY_CATEGORY.keys()}
    for slug, rows in KEYWORDS_BY_CATEGORY.items():
        for phrase, weight in rows:
            if phrase in text:
                scores[slug] += weight
    if "suc khoe" in text or "y te" in text:
        scores[CATEGORY_SLUGS["medical"]] += 1
    return scores


def _topic_category_slug(title: str, summary: str, source_name: str) -> str | None:
    scores = _topic_scores(title, summary, source_name)
    best_slug = max(scores.keys(), key=lambda slug: scores.get(slug, 0))
    best_score = scores.get(best_slug, 0)
    if best_score <= 0:
        return None

    # Tie-break: prefer specific categories over generic medical.
    priority = [
        CATEGORY_SLUGS["event"],
        CATEGORY_SLUGS["media"],
        CATEGORY_SLUGS["story"],
        CATEGORY_SLUGS["consult"],
        CATEGORY_SLUGS["medical"],
    ]
    top_slugs = {slug for slug, score in scores.items() if score == best_score}
    for slug in priority:
        if slug in top_slugs:
            return slug
    return best_slug


class Command(BaseCommand):
    help = "Sync news from trusted RSS feeds into NewsArticle."

    def add_arguments(self, parser):
        parser.add_argument("--max-items", type=int, default=3, help="Max items per feed.")
        parser.add_argument("--publish", action="store_true", help="Publish immediately.")
        parser.add_argument("--feed", action="append", dest="feeds", help="Custom RSS feed URL.")
        parser.add_argument(
            "--balanced",
            action="store_true",
            help="When topic is unclear, spread items across categories instead of using fallback category.",
        )
        parser.add_argument(
            "--fallback-category",
            type=str,
            default=CATEGORY_SLUGS["medical"],
            help="Fallback category slug when classifier cannot infer topic.",
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

        for category_name, category_slug in DEFAULT_NEWS_CATEGORIES:
            category, _ = NewsCategory.objects.get_or_create(
                slug=category_slug,
                defaults={"name": category_name},
            )
            if category.name != category_name:
                category.name = category_name
                category.save(update_fields=["name"])

        categories_by_slug = {c.slug: c for c in NewsCategory.objects.all()}
        if CATEGORY_SLUGS["medical"] not in categories_by_slug:
            self.stdout.write(self.style.ERROR("Missing required category 'tin-tuc-y-khoa'."))
            return

        fallback_slug = (options.get("fallback_category") or "").strip() or CATEGORY_SLUGS["medical"]
        if fallback_slug not in categories_by_slug:
            self.stdout.write(
                self.style.WARNING(
                    f"Fallback category '{fallback_slug}' not found. Use '{CATEGORY_SLUGS['medical']}' instead."
                )
            )
            fallback_slug = CATEGORY_SLUGS["medical"]

        bucket_order = [
            CATEGORY_SLUGS["consult"],
            CATEGORY_SLUGS["medical"],
            CATEGORY_SLUGS["media"],
            CATEGORY_SLUGS["story"],
            CATEGORY_SLUGS["event"],
        ]
        created_buckets = {slug: 0 for slug in bucket_order}
        existing_counts = {slug: 0 for slug in bucket_order}
        for row in (
            NewsArticle.objects.filter(category__slug__in=bucket_order)
            .values("category__slug")
            .annotate(n=Count("id"))
        ):
            existing_counts[row["category__slug"]] = int(row["n"])

        def _least_filled_slug() -> str:
            return min(bucket_order, key=lambda slug: existing_counts.get(slug, 0) + created_buckets.get(slug, 0))

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
                if item.source_url and NewsArticle.objects.filter(source_url=item.source_url).exists():
                    skipped_count += 1
                    continue
                if NewsArticle.objects.filter(title__iexact=item.title).exists():
                    skipped_count += 1
                    continue

                topic_slug = _topic_category_slug(item.title, item.summary, item.source_name)
                if topic_slug:
                    chosen_slug = topic_slug
                elif balanced:
                    chosen_slug = _least_filled_slug()
                else:
                    chosen_slug = fallback_slug

                target_category = categories_by_slug.get(chosen_slug) or categories_by_slug[fallback_slug]
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
                    published_at = item.published_at
                    if timezone.is_naive(published_at):
                        published_at = timezone.make_aware(published_at, timezone.get_current_timezone())
                    article.published_at = published_at
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

