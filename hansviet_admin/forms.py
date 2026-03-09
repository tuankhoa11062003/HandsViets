from django import forms
from django.utils.text import slugify
from .models import Service, ServiceCategory, NewsArticle, NewsCategory


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
