import re


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or "", flags=re.UNICODE))


def _strip_html(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    return clean_text(no_tags)


def ensure_summary(title: str, summary: str, min_len: int = 260, min_words: int = 55) -> str:
    s = clean_text(summary)
    if len(s) >= min_len and _word_count(s) >= min_words:
        return s
    fallback = (
        f"{title}. {s} "
        "Bài viết này được biên tập theo hướng thực hành cho người đọc Việt Nam, "
        "làm rõ bối cảnh bệnh lý, dấu hiệu cần theo dõi, nhóm nguy cơ và các bước xử trí phù hợp. "
        "Nội dung cũng nhấn mạnh thời điểm cần đi khám, cách phối hợp cùng bác sĩ điều trị, "
        "vai trò của phục hồi chức năng và các lưu ý để hạn chế biến chứng trong sinh hoạt hằng ngày."
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
    min_words: int = 420,
) -> str:
    base = (content or "").strip()
    if image_url and "<img" not in base.lower():
        base = (
            f'<figure><img src="{image_url}" alt="{title}" />'
            f"<figcaption>Ảnh minh họa từ nguồn tham khảo</figcaption></figure>\n\n"
            + base
        )

    normalized_base = _strip_html(base)
    if len(normalized_base) >= min_len and _word_count(normalized_base) >= min_words:
        return base

    category_label = category_name or "Tin tức Y khoa"
    source_label = source_name or "Nguồn tham khảo"
    source_link = (
        f'<a href="{source_url}" target="_blank" rel="noopener noreferrer">{source_label}</a>'
        if source_url
        else source_label
    )
    s = ensure_summary(title, summary)

    appendix_sections = [
        "<h2>Tổng quan vấn đề</h2>"
        f"<p>{s}</p>"
        f"<p>Nội dung thuộc chuyên mục <strong>{category_label}</strong>, ưu tiên tính chính xác, dễ hiểu và có thể áp dụng trong chăm sóc sức khỏe hằng ngày.</p>",
        "<h2>Dấu hiệu nhận biết và nhóm nguy cơ</h2>"
        "<ul>"
        "<li>Theo dõi dấu hiệu xuất hiện kéo dài, tái phát hoặc tăng dần mức độ.</li>"
        "<li>Lưu ý bệnh nền, tuổi tác, mức độ vận động, giấc ngủ và dinh dưỡng.</li>"
        "<li>Đánh giá yếu tố nghề nghiệp và thói quen sinh hoạt có thể làm triệu chứng nặng hơn.</li>"
        "</ul>",
        "<h2>Định hướng xử trí ban đầu</h2>"
        "<p>Không tự ý dùng thuốc kéo dài khi chưa có chỉ định chuyên môn. "
        "Nếu triệu chứng ảnh hưởng sinh hoạt, cần khám sớm để được đánh giá nguyên nhân và lập kế hoạch điều trị phù hợp.</p>"
        "<p>Trong giai đoạn phục hồi, nên duy trì vận động phù hợp, theo dõi đáp ứng điều trị, "
        "và tái khám định kỳ để điều chỉnh phác đồ khi cần.</p>",
        "<h2>Khuyến nghị thực hành cho người bệnh và gia đình</h2>"
        "<ul>"
        "<li>Ghi lại triệu chứng theo mốc thời gian để cung cấp cho bác sĩ.</li>"
        "<li>Ưu tiên lối sống lành mạnh: ngủ đủ, ăn cân bằng, tránh căng thẳng kéo dài.</li>"
        "<li>Tuân thủ lịch tập phục hồi chức năng và hướng dẫn an toàn tại nhà.</li>"
        "<li>Chủ động hỏi lại nhân viên y tế khi chưa rõ kế hoạch điều trị.</li>"
        "</ul>",
        "<h2>Lưu ý chuyên môn</h2>"
        "<p>Thông tin trong bài có giá trị tham khảo và không thay thế chẩn đoán trực tiếp. "
        "Mọi quyết định điều trị cần dựa trên thăm khám thực tế và chỉ định của bác sĩ.</p>",
        f"<h2>Nguồn tham khảo</h2><p>{source_link}</p>",
    ]

    assembled = (base + "\n\n" + "\n\n".join(appendix_sections)).strip() if base else "\n\n".join(appendix_sections)

    extra_block = (
        "<h2>Phân tích mở rộng</h2>"
        f"<p>{s}</p>"
        "<p>Ở góc độ phòng ngừa, người đọc nên duy trì theo dõi sức khỏe định kỳ, "
        "nhận diện sớm dấu hiệu bất thường và trao đổi với bác sĩ trước khi thay đổi thuốc hoặc cường độ vận động. "
        "Việc phối hợp giữa điều trị y khoa và phục hồi chức năng thường giúp cải thiện kết quả dài hạn.</p>"
    )

    for _ in range(6):
        normalized = _strip_html(assembled)
        if len(normalized) >= min_len and _word_count(normalized) >= min_words:
            break
        assembled = f"{assembled}\n\n{extra_block}".strip()

    return assembled

