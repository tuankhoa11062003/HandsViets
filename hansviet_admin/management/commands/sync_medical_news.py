import imghdr
import re
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from hansviet_admin.models import NewsArticle, NewsCategory
from hansviet_admin.services.news_content import ensure_detailed_content, ensure_summary
from hansviet_admin.services.perplexity_news import fetch_category_news, unique_article_slug


DEFAULT_CATEGORY_SLUGS = [
    "tin-tuc-y-khoa",
    "tu-van-phcn",
    "tin-truyen-thong",
    "khuyen-mai-su-kien",
    "cau-chuyen-khach-hang",
]


class Command(BaseCommand):
    help = "Sync medical news from Perplexity-compatible API and save into NewsArticle."

    def add_arguments(self, parser):
        parser.add_argument("--category", action="append", dest="categories", help="Category slug to sync.")
        parser.add_argument("--max-items", type=int, default=3, help="Max items per category.")
        parser.add_argument("--publish", action="store_true", help="Publish immediately.")
        parser.add_argument("--model", type=str, default="", help="Override model for this run.")

    def handle(self, *args, **options):
        def _extract_og_image(source_url: str) -> str:
            if not source_url:
                return ""
            try:
                req = Request(source_url, headers={"User-Agent": "Mozilla/5.0 (HandsViet News Bot)"})
                with urlopen(req, timeout=settings.PPLX_TIMEOUT) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                match = re.search(
                    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                    html,
                    flags=re.IGNORECASE,
                )
                return (match.group(1).strip() if match else "")
            except Exception:
                return ""

        def _download_image_file(url: str, title: str) -> ContentFile | None:
            if not url:
                return None
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0 (HandsViet News Bot)"})
                with urlopen(req, timeout=settings.PPLX_TIMEOUT) as resp:
                    data = resp.read()
                if not data:
                    return None
                kind = imghdr.what(None, h=data) or "jpg"
                if kind == "jpeg":
                    kind = "jpg"
                safe_title = "".join(ch if ch.isalnum() else "-" for ch in (title or "news-image")).strip("-").lower()
                safe_title = safe_title[:50] or "news-image"
                name = f"{safe_title}-{timezone.now().strftime('%Y%m%d%H%M%S')}.{kind}"
                cf = ContentFile(data)
                cf.name = name
                return cf
            except Exception:
                return None

        category_slugs = options.get("categories") or DEFAULT_CATEGORY_SLUGS
        max_items = max(1, options["max_items"])
        auto_publish = bool(options.get("publish")) or settings.PPLX_AUTO_PUBLISH
        model_override = (options.get("model") or "").strip()
        if model_override:
            settings.PPLX_MODEL = model_override

        created_count = 0
        skipped_count = 0

        for slug in category_slugs:
            category = NewsCategory.objects.filter(slug=slug).first()
            if not category:
                self.stdout.write(self.style.WARNING(f"Skip '{slug}': category not found."))
                continue

            self.stdout.write(f"Syncing category: {slug}")
            try:
                items = fetch_category_news(category.name, max_items=max_items)
            except Exception as ex:
                self.stdout.write(self.style.ERROR(f"Error fetching '{slug}': {ex}"))
                continue

            for item in items:
                if item.source_url and NewsArticle.objects.filter(source_url=item.source_url).exists():
                    skipped_count += 1
                    continue
                if NewsArticle.objects.filter(title__iexact=item.title).exists():
                    skipped_count += 1
                    continue

                slug_value = unique_article_slug(item.title, exists_fn=lambda s: NewsArticle.objects.filter(slug=s).exists())
                image_url = (item.image_url or "").strip()
                if not image_url and item.source_url:
                    image_url = _extract_og_image(item.source_url)

                article = NewsArticle.objects.create(
                    category=category,
                    title=item.title,
                    slug=slug_value,
                    summary=ensure_summary(item.title, item.summary),
                    content=ensure_detailed_content(
                        title=item.title,
                        summary=item.summary,
                        content=item.content or "",
                        source_url=item.source_url,
                        source_name=item.source_name,
                        category_name=category.name,
                        image_url=image_url,
                    ),
                    is_published=auto_publish,
                    source_url=item.source_url,
                    source_name=item.source_name,
                    ai_source="perplexity-compatible",
                    is_auto_generated=True,
                    needs_review=not auto_publish,
                )

                if item.published_at:
                    article.published_at = item.published_at
                    article.save(update_fields=["published_at"])

                if image_url:
                    image_file = _download_image_file(image_url, item.title)
                    if image_file:
                        article.thumbnail.save(image_file.name, image_file, save=True)
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created_count}, skipped={skipped_count}, "
                f"mode={'publish' if auto_publish else 'draft'}, at={timezone.now()}"
            )
        )

