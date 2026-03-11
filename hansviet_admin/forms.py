from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from urllib.parse import parse_qs, urlparse

from .models import Package, Service, ServiceCategory, NewsArticle, NewsCategory, Video

User = get_user_model()


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


class DashboardUserCreateForm(StyledFormMixin, forms.Form):
    ROLE_CHOICES = (
        ("staff", "Nhân viên"),
        ("user", "Người dùng"),
    )

    username = forms.CharField(max_length=150, label="Tên đăng nhập")
    first_name = forms.CharField(max_length=150, required=False, label="Họ")
    last_name = forms.CharField(max_length=150, required=False, label="Tên")
    email = forms.EmailField(required=False, label="Email")
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial="staff", label="Vai trò")
    password1 = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput())
    password2 = forms.CharField(label="Xác nhận mật khẩu", widget=forms.PasswordInput())
    is_active = forms.BooleanField(required=False, initial=True, label="Hoạt động")

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("Vui lòng nhập tên đăng nhập.")
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Tên đăng nhập đã tồn tại.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Mật khẩu xác nhận không khớp.")
        return cleaned_data

    def save(self):
        username = self.cleaned_data["username"]
        email = (self.cleaned_data.get("email") or "").strip()
        role = self.cleaned_data.get("role") or "staff"
        user = User.objects.create_user(
            username=username,
            email=email,
            password=self.cleaned_data["password1"],
        )
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.is_active = bool(self.cleaned_data.get("is_active"))
        user.is_staff = role == "staff"
        user.save()
        return user


class DashboardUserUpdateForm(StyledFormMixin, forms.ModelForm):
    ROLE_CHOICES = (
        ("staff", "Nhân viên"),
        ("user", "Người dùng"),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Vai trò")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "role", "is_active"]
        labels = {
            "first_name": "Họ",
            "last_name": "Tên",
            "email": "Email",
            "is_active": "Hoạt động",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance:
            self.fields["role"].initial = "staff" if instance.is_staff or instance.is_superuser else "user"
            if instance.is_superuser:
                self.fields["role"].disabled = True
                self.fields["role"].help_text = "Tài khoản superuser luôn thuộc nhóm quản trị."

    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.is_superuser:
            user.is_staff = (self.cleaned_data.get("role") == "staff")
        if commit:
            user.save()
        return user


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
    slug = forms.CharField(required=False)

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
            "provider_id": "Dán ID hoặc full URL YouTube/Vimeo, hệ thống sẽ tự nhận diện.",
            "is_active": "Bật để hiển thị video ngoài website.",
        }

    def clean_slug(self):
        title = self.cleaned_data.get("title", "")
        slug = self.cleaned_data.get("slug") or slugify(title, allow_unicode=False)
        slug = slugify(slug, allow_unicode=False)
        if not slug:
            raise forms.ValidationError("Slug không hợp lệ; vui lòng dùng chữ, số, dấu '-' hoặc '_'.")
        return _unique_slug(Video, slug, self.instance)

    def clean_provider_id(self):
        raw = (self.cleaned_data.get("provider_id") or "").strip()
        provider = self.cleaned_data.get("provider")
        if not raw:
            raise forms.ValidationError("Vui lòng nhập mã video hoặc URL.")

        if provider == Video.PROVIDER_YT:
            return self._extract_youtube_id(raw)
        if provider == Video.PROVIDER_VI:
            return self._extract_vimeo_id(raw)
        return raw

    def _extract_youtube_id(self, value):
        if "://" not in value:
            return value

        parsed = urlparse(value)
        host = (parsed.netloc or "").lower().replace("www.", "")
        path = parsed.path.strip("/")

        if host == "youtu.be" and path:
            return path.split("/")[0]
        if host in {"youtube.com", "m.youtube.com"}:
            if path == "watch":
                vid = parse_qs(parsed.query).get("v", [None])[0]
                if vid:
                    return vid
            if path.startswith("embed/") or path.startswith("shorts/"):
                return path.split("/", 1)[1].split("/")[0]

        raise forms.ValidationError("URL YouTube không hợp lệ.")

    def _extract_vimeo_id(self, value):
        if "://" not in value:
            return value
        parsed = urlparse(value)
        host = (parsed.netloc or "").lower().replace("www.", "")
        path = parsed.path.strip("/")
        if host == "vimeo.com" and path:
            return path.split("/")[0]
        if host == "player.vimeo.com" and path.startswith("video/"):
            return path.split("/", 1)[1].split("/")[0]
        raise forms.ValidationError("URL Vimeo không hợp lệ.")


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
            raise forms.ValidationError("Slug không hợp lệ; vui lòng dùng chữ, số, dấu '-' hoặc '_'.")
        return _unique_slug(Package, slug, self.instance)
