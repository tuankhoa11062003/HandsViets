import re


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def ensure_summary(title: str, summary: str, min_len: int = 220) -> str:
    s = clean_text(summary)
    if len(s) >= min_len:
        return s
    fallback = (
        f"{title}. {s} "
        "Bài viết cung cấp thêm bối cảnh y khoa, các yếu tố nguy cơ, dấu hiệu cần lưu ý, "
        "hướng xử trí phù hợp và khuyến nghị theo dõi sức khỏe cho người đọc."
    )
    return clean_text(fallback)


def ensure_detailed_content(
    title: str,
    summary: str,
    content: str,
    source_url: str = "",
    source_name: str = "",
    category_name: str = "",
    image_url: str = "",
    min_len: int = 2500,
) -> str:
    base = (content or "").strip()
    if image_url and "<img" not in base.lower():
        base = (
            f'<figure><img src="{image_url}" alt="{title}" />'
            f"<figcaption>Ảnh minh họa từ nguồn tham khảo</figcaption></figure>\n\n"
            + base
        )

    if len(clean_text(base)) >= min_len:
        return base

    category_label = category_name or "Tin tức y khoa"
    source_label = source_name or "Nguồn tham khảo"
    source_link = (
        f'<a href="{source_url}" target="_blank" rel="noopener noreferrer">{source_label}</a>'
        if source_url
        else source_label
    )
    s = ensure_summary(title, summary)
    appendix = f"""
<h2>Tổng quan vấn đề</h2>
<p>{s}</p>
<p>Ở góc nhìn cộng đồng, nội dung thuộc chuyên mục <strong>{category_label}</strong> có ý nghĩa trong việc giúp người đọc hiểu đúng bản chất vấn đề sức khỏe, tránh hoang mang và có quyết định chăm sóc phù hợp.</p>

<h2>Dấu hiệu nhận biết và yếu tố nguy cơ</h2>
<ul>
  <li>Theo dõi các dấu hiệu bất thường kéo dài hoặc tiến triển nặng dần.</li>
  <li>Chú ý tiền sử bệnh nền, tuổi tác, lối sống, mức độ vận động và chế độ dinh dưỡng.</li>
  <li>Đánh giá các yếu tố môi trường, nghề nghiệp và thói quen sinh hoạt có thể làm tăng nguy cơ.</li>
</ul>

<h2>Khuyến nghị thực hành cho người đọc</h2>
<ul>
  <li>Không tự ý điều trị khi chưa có tư vấn chuyên môn.</li>
  <li>Khám sớm khi triệu chứng ảnh hưởng sinh hoạt, công việc hoặc giấc ngủ.</li>
  <li>Duy trì vận động phù hợp, ngủ đủ giấc và ăn uống cân bằng.</li>
  <li>Theo dõi định kỳ và tái khám theo hướng dẫn của bác sĩ.</li>
</ul>

<h2>Lưu ý chuyên môn</h2>
<p>Nội dung này mang tính tham khảo, không thay thế chẩn đoán trực tiếp. Kế hoạch điều trị cần được cá nhân hóa theo tình trạng thực tế của từng người bệnh.</p>

<h2>Nguồn tham khảo</h2>
<p>{source_link}</p>
""".strip()

    if base:
        return f"{base}\n\n{appendix}"
    return appendix

