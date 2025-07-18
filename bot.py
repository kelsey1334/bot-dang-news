import os
import tempfile
import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from utils.excel_parser import parse_excel
from utils.gemini_api import write_article
from utils.wordpress_poster import post_to_wordpress
from utils.formatter import format_headings_and_keywords, clean_html_trailing_markdown, format_anchor_bold
from utils.image_utils import get_headline_img, download_resize_image, translate_alt, upload_featured_image, to_slug, add_logo_to_image, add_banner_to_image
import re
from utils.sinbyte_api import ping_sinbyte
import markdown2
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

PROMPT_TEMPLATE = """
Bạn là một chuyên gia viết nội dung tin tức bóng đá chuẩn SEO. Viết một bài blog dài khoảng 800 từ chuẩn SEO, hãy vào url {url} để lấy dữ liệu từ url này để viết bài, yêu cầu lấy đúng toàn bộ thông tin trong url để viết và không tự lấy thông cũ để thêm vào bài viết.
Trong bài viết, hãy tự nhiên chèn một liên kết nội bộ (internal link) với anchor text: "{anchor_text}" và url là: {url_anchor} ở một vị trí phù hợp (không phải ở đầu hoặc cuối bài, không được lặp lại), dùng đúng định dạng markdown [anchor_text]({url_anchor}).

Yêu cầu:

1. Cấu trúc bài viết:
- Chỉ có 1 thẻ H1 duy nhất, dưới 70 ký tự.
- Sapo mở đầu ngay sau tiêu đề bài viết: dài 150–200 ký tự.
- Có ít nhất 3 tiêu đề H2, mỗi H2 có 2-3 H3 bổ trợ, có thể có H4 nếu phù hợp.
- Yêu cầu phải sắp xếp các tiêu đề theo h1-h2-h3-h4... để đảm bảo cấu trúc chuẩn seo của bài viết.
⚠️Lưu ý: Viết bằng tiếng Việt, giọng văn rõ ràng, thực tế, sâu sắc. bắt đầu bài viết ngay lập tức, không có lời nói đầu và kết bài không thêm bất kỳ trích dẫn hoặc đường link nào, chỉ trả về nội dung bài viết.
"""

def extract_h1_and_remove(content):
    h1_md = re.search(r'^#\s*(.+)', content, re.MULTILINE)
    if h1_md:
        h1_text = h1_md.group(1).strip(' #*-')
        content_wo_h1 = re.sub(r'^#\s*.+\n?', '', content, count=1, flags=re.MULTILINE)
        return h1_text, content_wo_h1
    h1_html = re.search(r'<h1.*?>(.*?)</h1>', content, re.DOTALL | re.IGNORECASE)
    if h1_html:
        h1_text = h1_html.group(1).strip(' #*-')
        content_wo_h1 = re.sub(r'<h1.*?>.*?</h1>', '', content, count=1, flags=re.DOTALL | re.IGNORECASE)
        return h1_text, content_wo_h1
    first_line = content.split('\n', 1)[0].strip(' #*-')[:70]
    content_wo_first = content[len(first_line):].lstrip('\n')
    return first_line, content_wo_first

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Gửi file Excel (.xlsx) theo cấu trúc:\n"
        "Sheet 'tai_khoan': website | username | password | logo_url | banner_url\n"
        "Sheet 'key_word': url_nguon | website | chuyen_muc | anchor | url_anchor"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith('.xlsx'):
        await update.message.reply_text("❌ Chỉ nhận file Excel định dạng .xlsx")
        return

    await update.message.reply_text("🗂️ Đang tải file Excel...")

    file = await doc.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tf:
        file_path = tf.name
        await file.download_to_drive(custom_path=file_path)
        await update.message.reply_text("🗂️ Đang đọc và phân tích file...")

        try:
            accounts, posts = parse_excel(file_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi đọc file: {e}")
            os.unlink(file_path)
            return

        results = []
        website_links = dict()  # {website: [list post_url]}
        total = len(posts)
        for idx, post in posts.iterrows():
            stt = idx + 1
            url_nguon = post['url_nguon']
            website = post['website']
            chuyen_muc = int(post['chuyen_muc'])
            anchor_text = post['anchor'] if 'anchor' in post else ''
            url_anchor = post['url_anchor'] if 'url_anchor' in post else ''
            acc = accounts.loc[accounts['website'] == website]
            if acc.empty:
                results.append(f"{website}: Không tìm thấy tài khoản")
                continue
            acc = acc.iloc[0]
            username = acc['username']
            password = acc['password']
            logo_url = acc['logo_url'] if 'logo_url' in acc else None
            banner_url = acc['banner_url'] if 'banner_url' in acc else None

            await update.message.reply_text(f"🌐 [{stt}/{total}] Đang xử lý website: <b>{website}</b>", parse_mode='HTML')
            prompt = PROMPT_TEMPLATE.format(
                url=url_nguon,
                anchor_text=anchor_text,
                url_anchor=url_anchor
            )
            try:
                await update.message.reply_text(f"🤖 Đang viết bài AI cho <b>{website}</b>...", parse_mode='HTML')
                content = write_article(prompt)
                h1_keyword, content_wo_h1 = extract_h1_and_remove(content)
                await update.message.reply_text(f"🏷️ Đang xử lý format bài viết...", parse_mode='HTML')
                html = markdown2.markdown(content_wo_h1)
                html = format_headings_and_keywords(html, h1_keyword)
                html = format_anchor_bold(html, anchor_text)
                html = clean_html_trailing_markdown(html)

                await update.message.reply_text("🖼️ Đang lấy ảnh đầu bài...")
                src_img, alt_img = get_headline_img(url_nguon)
                featured_media_id = None
                if src_img:
                    alt_vi = translate_alt(alt_img) if alt_img else ""
                    slug = to_slug(alt_vi) if alt_vi else f"thumb-{idx}"
                    img_path = f"/tmp/{slug}.jpg"
                    await update.message.reply_text("🎨 Đang resize/chèn logo/banner vào ảnh...")
                    download_resize_image(src_img, img_path)
                    if logo_url and logo_url.startswith("http"):
                        out_path = f"/tmp/{slug}_logo.jpg"
                        add_logo_to_image(img_path, logo_url, out_path)
                        img_path = out_path
                    if banner_url and banner_url.startswith("http"):
                        out_path = f"/tmp/{slug}_banner.jpg"
                        add_banner_to_image(img_path, banner_url, out_path)
                        img_path = out_path
                    await update.message.reply_text("⬆️ Đang upload ảnh lên WordPress...")
                    try:
                        featured_media_id = upload_featured_image(
                            website, username, password, img_path, alt_vi
                        )
                    except Exception as e:
                        await update.message.reply_text(f"❌ Lỗi upload ảnh thumbnail: {e}")
                        featured_media_id = None

                await update.message.reply_text("🚀 Đang đăng bài lên WordPress...")
                post_url = post_to_wordpress(
                    website, username, password, html, chuyen_muc, h1_keyword, featured_media_id
                )
                await update.message.reply_text(f"✅ <b>{website}</b>: Đăng thành công!\n🔗 {post_url}", parse_mode='HTML')
                
                # Gom link vào website_links
                if website not in website_links:
                    website_links[website] = []
                website_links[website].append(post_url)

                results.append(f"{website}: Đăng thành công ({post_url})")
            except Exception as e:
                await update.message.reply_text(f"❌ <b>{website}</b>: Lỗi {e}", parse_mode='HTML')
                results.append(f"{website}: Lỗi {e}")

        # Sau khi xong, ép index cho từng website (batch 1 lần)
        for website, urls in website_links.items():
            now = datetime.datetime.now().strftime("%H-%M-%d-%m-%Y")
            dripfeed = f"Noridc"
            name = website
            await update.message.reply_text(f"⚡ Đang gửi batch {len(urls)} link vừa đăng của {website} lên Sinbyte ép index...")
            ok, msg = ping_sinbyte(urls, name, dripfeed)
            if ok:
                await update.message.reply_text(f"🟢 Sinbyte: Ép index thành công cho {website}!")
            else:
                await update.message.reply_text(f"🟠 Sinbyte: Gửi batch link {website} lỗi: {msg}")

        await update.message.reply_text("📝 Đã hoàn thành tất cả công việc.")
        os.unlink(file_path)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()

if __name__ == "__main__":
    main()
