import os
import tempfile
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from utils.excel_parser import parse_excel
from utils.gemini_api import write_article
from utils.wordpress_poster import post_to_wordpress
from utils.formatter import format_headings_and_keywords, clean_html_trailing_markdown
from utils.image_utils import get_headline_img, download_resize_image, translate_alt, upload_featured_image, to_slug
import markdown2
import re
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

PROMPT_TEMPLATE = """
Bạn là một chuyên gia viết nội dung tin tức bóng đá chuẩn SEO. Viết một bài blog dài khoảng 800 từ chuẩn SEO, hãy vào url {url} để lấy dữ liệu từ url này để viết bài, yêu cầu lấy đúng toàn bộ thông tin trong url để viết và không tự lấy thông cũ để thêm vào bài viết.

Yêu cầu:

1. Cấu trúc bài viết:

- Chỉ có 1 thẻ H1 duy nhất, dưới 70 ký tự.

- Sapo mở đầu ngay sau tiêu đề bài viết: dài 150–200 ký tự.

2. Thân bài:

- Có ít nhất 3 tiêu đề H2, mỗi H2 có 2-3 H3 bổ trợ, có thể có H4 nếu phù hợp

3. Vấn đề nội dung
- Nếu trong url đấy có nội dung về lịch trình hay một time line hay một thống kê nào đó, thì hãy tạo một bảng có định chuẩn để tôi copy và đăng lên wordpress không bị lỗi, không được tạo bảng dạng như thế này: | Thành phố | Sân vận động | Sức chứa |
| :————– | :—————– | :——- |
| Basel | St. Jakob-Park | 38.500 |
| Bern | Stadion Wankdorf | 32.000 |
| Geneva | Stade de Genève | 30.000 |
| Lucerne | Swissporarena | 16.800 |
| Sion | Stade Tourbillon | 16.000 |
| St. Gallen | kybunpark | 19.500 |
| Thun | Stockhorn Arena | 10.000 |
| Zurich | Letzigrund | 26.000 |.

⚠️Lưu ý: Viết bằng tiếng Việt, giọng văn rõ ràng, thực tế, sâu sắc. bắt đầu bài viết ngay lập tức, không có lời nói đầu và kết bài không thêm bất kỳ trích dẫn hoặc đường link nào, chỉ trả về nội dung bài viết.
"""

def extract_h1_and_remove(content):
    """
    Trích xuất H1 đầu tiên (markdown hoặc HTML), trả về (h1, content đã loại bỏ H1)
    """
    h1_md = re.search(r'^#\s*(.+)', content, re.MULTILINE)
    if h1_md:
        h1_text = h1_md.group(1).strip()
        content_wo_h1 = re.sub(r'^#\s*.+\n?', '', content, count=1, flags=re.MULTILINE)
        return h1_text, content_wo_h1
    h1_html = re.search(r'<h1.*?>(.*?)</h1>', content, re.DOTALL | re.IGNORECASE)
    if h1_html:
        h1_text = h1_html.group(1).strip()
        content_wo_h1 = re.sub(r'<h1.*?>.*?</h1>', '', content, count=1, flags=re.DOTALL | re.IGNORECASE)
        return h1_text, content_wo_h1
    first_line = content.split('\n', 1)[0].strip()[:70]
    content_wo_first = content[len(first_line):].lstrip('\n')
    return first_line, content_wo_first

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Gửi file Excel (.xlsx) theo cấu trúc:\n"
        "Sheet 'tai_khoan': website | username | password\n"
        "Sheet 'key_word': url_nguon | website | chuyen_muc (ID số)"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith('.xlsx'):
        await update.message.reply_text("Chỉ nhận file Excel định dạng .xlsx")
        return

    file = await doc.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tf:
        file_path = tf.name
        await file.download_to_drive(custom_path=file_path)
        await update.message.reply_text("Đang xử lý file...")

        try:
            accounts, posts = parse_excel(file_path)
        except Exception as e:
            await update.message.reply_text(f"Lỗi đọc file: {e}")
            os.unlink(file_path)
            return

        results = []
        for idx, post in posts.iterrows():
            url_nguon = post['url_nguon']
            website = post['website']
            chuyen_muc = int(post['chuyen_muc'])
            acc = accounts.loc[accounts['website'] == website]
            if acc.empty:
                results.append(f"{website}: Không tìm thấy tài khoản")
                continue
            acc = acc.iloc[0]
            username = acc['username']
            password = acc['password']

            prompt = PROMPT_TEMPLATE.format(url=url_nguon)
            try:
                # Viết bài bằng AI
                content = write_article(prompt)
                h1_keyword, content_wo_h1 = extract_h1_and_remove(content)
                html = markdown2.markdown(content_wo_h1)
                html = format_headings_and_keywords(html, h1_keyword)
                html = clean_html_trailing_markdown(html)
                # ==== XỬ LÝ ẢNH THUMBNAIL ====
                src_img, alt_img = get_headline_img(url_nguon)
                featured_media_id = None
                if src_img:
                    alt_vi = translate_alt(alt_img) if alt_img else ""
                    slug = to_slug(alt_vi) if alt_vi else f"thumb-{idx}"
                    img_path = f"/tmp/{slug}.jpg"
                    download_resize_image(src_img, img_path)
                    try:
                        featured_media_id = upload_featured_image(
                            website, username, password, img_path, alt_vi
                        )
                    except Exception as e:
                        print(f"Lỗi upload ảnh thumbnail: {e}")
                        featured_media_id = None

                post_url = post_to_wordpress(
                    website, username, password, html, chuyen_muc, h1_keyword, featured_media_id
                )
                results.append(f"{website}: Đăng thành công ({post_url})")
            except Exception as e:
                results.append(f"{website}: Lỗi {e}")

        await update.message.reply_text("\n".join(results))
        os.unlink(file_path)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()

if __name__ == "__main__":
    main()
