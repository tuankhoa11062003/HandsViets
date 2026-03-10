import html

from django.core.management.base import BaseCommand

from hansviet_admin.models import NewsArticle


def repair_text(value: str) -> str:
    text = html.unescape((value or "").strip())
    for _ in range(2):
        if not any(tok in text for tok in ("Ã", "Ä", "Â", "á»", "áº", "&amp;", "&#")):
            break
        try:
            candidate = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            break
        if candidate and candidate != text:
            text = candidate
        else:
            break
    return text


class Command(BaseCommand):
    help = "Fix mojibake and HTML entities in existing NewsArticle title/summary/content/source_name."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="0 means all.")

    def handle(self, *args, **options):
        qs = NewsArticle.objects.all().order_by("-id")
        limit = int(options["limit"])
        updated = 0
        scanned = 0

        for article in qs:
            scanned += 1
            if limit > 0 and scanned > limit:
                break

            old_title = article.title or ""
            old_summary = article.summary or ""
            old_content = article.content or ""
            old_source = article.source_name or ""

            new_title = repair_text(old_title)
            new_summary = repair_text(old_summary)
            new_content = repair_text(old_content)
            new_source = repair_text(old_source)

            if (new_title, new_summary, new_content, new_source) != (old_title, old_summary, old_content, old_source):
                article.title = new_title
                article.summary = new_summary
                article.content = new_content
                article.source_name = new_source
                article.save(update_fields=["title", "summary", "content", "source_name"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Fix done. updated={updated}, scanned={scanned}"))

