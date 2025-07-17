import os
import tempfile
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from utils.excel_parser import parse_excel
from utils.gemini_api import write_article
from utils.wordpress_poster import post_to_wordpress
from utils.formatter import format_headings_and_keywords
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

⚠️Lưu ý: Viết bằng tiếng Việt, giọng văn rõ ràng, thực tế, sâu sắc, Không thêm bất kỳ trích dẫn hoặc đường link nào, chỉ trả về nội dung bài viết.
"""

def extract_h1_and_remove(content):
    # 1. Tìm H1 dạng markdown "# ..."
    h1_md = re.search(r'^#\s*(.+)', content, re.MULTILINE)
    if h1_md:
        h1_text = h1_md.group(1).strip()
        content_wo_h1 = re.sub(r'^#\s*.+\n?', '', content, count=1, flags=re.MULTILINE)
        return h1_text, content_wo_h1
    # 2. Tìm H1 dạng HTML
    h1_html = re.search(r'<h1.*?>(.*?)</h1>', content, re.DOTALL | re.IGNORECASE)
    if h1_html:
        h1_text = h1_html.group(1).strip()
        content_wo_h1 = re.sub(r'<h1.*?>.*?</h1>', '', content, count=1, flags=re.DOTALL | re.IGNORECASE)
        return h1_text, content_wo_h1
    # 3. Nếu không có, lấy dòng đầu
    first_line = content.split('\n', 1)[0].strip()[:70]
    content_wo_first = content[len(first_line):].lstrip('\n')
    return first_line, content_wo_first

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gửi file Excel (.xlsx) theo cấu trúc:\n"
                                    "Sheet 'tai_khoan': website | username | password\n"
                                    "Sheet 'key_word': url_nguon | website | chuyen_muc (ID số)")

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
                content = write_article(prompt)  # content dạng markdown/text
                h1_keyword, content_wo_h1 = extract_h1_and_remove(content)
                html = markdown2.markdown(content_wo_h1)
                html = format_headings_and_keywords(html, h1_keyword)
                post_url = post_to_wordpress(website, username, password, html, chuyen_muc)
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
