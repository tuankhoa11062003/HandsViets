from django import forms
from django.utils.text import slugify
from .models import Package, Service, ServiceCategory, NewsArticle, NewsCategory, Video


def _unique_slug(model, slug_base, instance=None):
    """
    Tạo slug duy nhất cho model, thêm hậu tố -2, -3... nếu trùng.
    """
    slug = slug_base
    idx = 2
    qs = model.objects.filter(slug__iexact=slug)
    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.exists():
        slug = f"{slug_base}-{idx}"
        qs = model.objects.filter(slug__iexact=slug)
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        idx += 1
    return slug


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "h-5 w-5 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
            else:
                field.widget.attrs["class"] = (
                    "w-full px-4 py-3 rounded-xl border border-slate-200 "
                    "focus:outline-none focus:ring-2 focus:ring-teal-200 focus:border-teal-500"
                )


class ServiceCategoryForm(forms.ModelForm):
    class Meta:
        model = ServiceCategory
        fields = ["name", "slug", "description", "icon_svg", "order"]

    def clean_slug(self):
        name = self.cleaned_data.get("name", "")
        slug = self.cleaned_data.get("slug") or slugify(name, allow_unicode=False)
        slug = slugify(slug, allow_unicode=False)
        if not slug:
            raise forms.ValidationError("Slug không hợp lệ; vui lòng dùng chữ, số, dấu '-' hoặc '_'.")
        return _unique_slug(ServiceCategory, slug, self.instance)


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            "title",
            "slug",
            "category",
            "summary",
            "price_text",
            "duration",
            "featured_tag",
            "is_featured",
            "order",
            "thumbnail",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_slug(self):
        title = self.cleaned_data.get("title", "")
        slug = self.cleaned_data.get("slug") or slugify(title, allow_unicode=False)
        slug = slugify(slug, allow_unicode=False)
        if not slug:
            raise forms.ValidationError("Slug không hợp lệ; vui lòng dùng chữ, số, dấu '-' hoặc '_'.")
        return _unique_slug(Service, slug, self.instance)


class NewsCategoryForm(forms.ModelForm):
    class Meta:
        model = NewsCategory
        fields = ["name", "slug"]

    def clean_slug(self):
        name = self.cleaned_data.get("name", "")
        slug = self.cleaned_data.get("slug") or slugify(name, allow_unicode=False)
        slug = slugify(slug, allow_unicode=False)
        if not slug:
            raise forms.ValidationError("Slug không hợp lệ; vui lòng dùng chữ, số, dấu '-' hoặc '_'.")
        return _unique_slug(NewsCategory, slug, self.instance)


class NewsArticleForm(forms.ModelForm):
    class Meta:
        model = NewsArticle
        fields = [
            "title",
            "slug",
            "category",
            "summary",
            "content",
            "thumbnail",
            "is_published",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 3}),
            "content": forms.Textarea(attrs={"rows": 10, "class": "ckeditor"}),
        }

    def clean_slug(self):
        title = self.cleaned_data.get("title", "")
        slug = self.cleaned_data.get("slug") or slugify(title, allow_unicode=False)
        slug = slugify(slug, allow_unicode=False)
        if not slug:
            raise forms.ValidationError("Slug không hợp lệ; vui lòng dùng chữ, số, dấu '-' hoặc '_'.")
        return _unique_slug(NewsArticle, slug, self.instance)


class VideoForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Video
        fields = [
            "title",
            "slug",
            "provider",
            "provider_id",
            "access",
            "duration",
            "category",
            "is_active",
        ]
        labels = {
            "title": "Tên video",
            "slug": "Đường dẫn (slug)",
            "provider": "Nền tảng",
            "provider_id": "Mã video",
            "access": "Quyền truy cập",
            "duration": "Thời lượng",
            "category": "Danh mục",
            "is_active": "Đang hoạt động",
        }
        help_texts = {
            "provider_id": "Ví dụ YouTube: dQw4w9WgXcQ, Vimeo: 123456789",
            "is_active": "Bật để hiển thị video ngoài website.",
        }

    def clean_slug(self):
        title = self.cleaned_data.get("title", "")
        slug = self.cleaned_data.get("slug") or slugify(title, allow_unicode=False)
        slug = slugify(slug, allow_unicode=False)
        if not slug:
            raise forms.ValidationError("Slug khÃ´ng há»£p lá»‡; vui lÃ²ng dÃ¹ng chá»¯, sá»‘, dáº¥u '-' hoáº·c '_'.")
        return _unique_slug(Video, slug, self.instance)


class PackageForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Package
        fields = ["name", "slug", "description", "duration_days", "price", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "name": "Tên gói liệu pháp",
            "slug": "Đường dẫn (slug)",
            "description": "Mô tả",
            "duration_days": "Thời lượng (ngày)",
            "price": "Giá",
            "is_active": "Đang hoạt động",
        }
        help_texts = {
            "is_active": "Bật để cho phép người dùng mua gói này.",
        }

    def clean_slug(self):
        name = self.cleaned_data.get("name", "")
        slug = self.cleaned_data.get("slug") or slugify(name, allow_unicode=False)
        slug = slugify(slug, allow_unicode=False)
        if not slug:
            raise forms.ValidationError("Slug khÃ´ng há»£p lá»‡; vui lÃ²ng dÃ¹ng chá»¯, sá»‘, dáº¥u '-' hoáº·c '_'.")
        return _unique_slug(Package, slug, self.instance)
