import unicodedata

from django.core.management.base import BaseCommand
from django.db.models import Count

from hansviet_admin.models import NewsArticle, NewsCategory


CATEGORY_SLUGS = {
    "story": "cau-chuyen-khach-hang",
    "event": "khuyen-mai-su-kien",
    "media": "tin-truyen-thong",
    "medical": "tin-tuc-y-khoa",
    "consult": "tu-van-phcn",
}
CATEGORY_ORDER = [
    CATEGORY_SLUGS["story"],
    CATEGORY_SLUGS["event"],
    CATEGORY_SLUGS["media"],
    CATEGORY_SLUGS["medical"],
    CATEGORY_SLUGS["consult"],
]


def _normalize_text(text: str) -> str:
    base = (text or "").lower()
    base = "".join(ch for ch in unicodedata.normalize("NFD", base) if unicodedata.category(ch) != "Mn")
    return base.replace("đ", "d").replace("Đ", "D")


def pick_topic_category_slug(title: str, summary: str, source_name: str) -> str | None:
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


def _least_filled_slug(total_counts: dict[str, int], changed_counts: dict[str, int]) -> str:
    return min(
        CATEGORY_ORDER,
        key=lambda slug: (total_counts.get(slug, 0) + changed_counts.get(slug, 0), changed_counts.get(slug, 0)),
    )


class Command(BaseCommand):
    help = "Reclassify existing news articles by topic; optional rebalance across categories."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="0 means all.")
        parser.add_argument("--only-auto", action="store_true", help="Only auto-generated articles.")
        parser.add_argument("--rebalance", action="store_true", help="Balance uncategorized items across all categories.")

    def handle(self, *args, **options):
        categories = {c.slug: c for c in NewsCategory.objects.all()}
        missing = [slug for slug in CATEGORY_ORDER if slug not in categories]
        if missing:
            self.stdout.write(self.style.ERROR(f"Missing categories: {', '.join(missing)}"))
            return

        qs = NewsArticle.objects.select_related("category").all().order_by("-id")
        if options["only_auto"]:
            qs = qs.filter(is_auto_generated=True)

        total_counts = {slug: 0 for slug in CATEGORY_ORDER}
        for row in (
            NewsArticle.objects.filter(category__slug__in=CATEGORY_ORDER)
            .values("category__slug")
            .annotate(n=Count("id"))
        ):
            total_counts[row["category__slug"]] = int(row["n"])
        changed_counts = {slug: 0 for slug in CATEGORY_ORDER}

        changed = 0
        scanned = 0
        limit = int(options["limit"])

        for article in qs:
            scanned += 1
            if limit > 0 and scanned > limit:
                break

            topic_slug = pick_topic_category_slug(article.title, article.summary, article.source_name)
            if topic_slug:
                target_slug = topic_slug
            elif options["rebalance"]:
                target_slug = _least_filled_slug(total_counts, changed_counts)
            else:
                target_slug = CATEGORY_SLUGS["medical"]

            target_category = categories[target_slug]
            if article.category_id != target_category.id:
                article.category = target_category
                article.save(update_fields=["category"])
                changed += 1
                changed_counts[target_slug] += 1

        self.stdout.write(self.style.SUCCESS(f"Reclassify done. changed={changed}, scanned={scanned}"))

