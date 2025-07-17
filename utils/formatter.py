import re

def format_headings_and_keywords(html, keyword):
    # Bọc nội dung heading H1–H4 bằng <strong> nếu chưa có strong
    def bold_heading_content(match):
        text = match.group(2)
        if '<strong>' in text:
            return f"<{match.group(1)}>{text}</{match.group(1)}>"
        return f"<{match.group(1)}><strong>{text}</strong></{match.group(1)}>"
    html = re.sub(r'<(h[1-4])>(.*?)</\1>', bold_heading_content, html, flags=re.DOTALL)

    # In đậm từ khoá (tránh strong lồng strong)
    html = re.sub(
        fr'(?i)(?<!<strong>){re.escape(keyword)}(?!</strong>)',
        lambda m: f'<strong>{m.group(0)}</strong>',
        html
    )
    # Loại strong lồng nhau nếu có
    html = re.sub(r'(<strong>)+\s*(.*?)\s*(</strong>)+', r'<strong>\2</strong>', html)
    return html
