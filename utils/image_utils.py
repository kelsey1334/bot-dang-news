import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import os
from googletrans import Translator
import re
import unidecode

def get_headline_img(url):
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    span = soup.find('span', {'aria-label': 'Image Headline'})
    if not span:
        return None, None
    img = span.find('img')
    if not img:
        return None, None
    src = img.get('src')
    alt = img.get('alt', '')
    return src, alt

def download_resize_image(img_url, save_path):
    resp = requests.get(img_url, stream=True, timeout=10)
    img = Image.open(BytesIO(resp.content)).convert('RGB')
    img = img.resize((800, 400))
    # Nén về dưới 100kb
    quality = 90
    while True:
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=quality)
        if buffer.tell() <= 102400 or quality <= 30:
            break
        quality -= 5
    with open(save_path, 'wb') as f:
        f.write(buffer.getvalue())
    return save_path

def translate_alt(text):
    if not text.strip():
        return ""
    return GoogleTranslator(source='auto', target='vi').translate(text)
    
def to_slug(text):
    text = unidecode.unidecode(text)
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = re.sub(r'-+', '-', text)
    text = text.strip('-')
    return text[:50] or "image"
    
def upload_featured_image(wp_url, username, password, img_path, alt_text):
    media_api = wp_url.rstrip('/') + "/wp-json/wp/v2/media"
    with open(img_path, 'rb') as img_file:
        files = {'file': (os.path.basename(img_path), img_file, 'image/jpeg')}
        data = {'alt_text': alt_text}
        resp = requests.post(media_api, files=files, data=data,
                             auth=(username, password))
    resp.raise_for_status()
    resp_json = resp.json()
    return resp_json['id']
