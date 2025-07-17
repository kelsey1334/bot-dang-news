import requests
from requests.auth import HTTPBasicAuth
import re

def extract_h1(content):
    # Tìm H1 ở dạng markdown (# Tiêu đề)
    match = re.search(r'^\s*#\s+(.{1,70})', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    # Hoặc tìm <h1>Tiêu đề</h1>
    match = re.search(r'<h1[^>]*>(.{1,70})<\/h1>', content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Nếu không có, lấy dòng đầu tiên tối đa 70 ký tự
    return content.split('\n', 1)[0].strip()[:70]

def post_to_wordpress(url, username, password, content, category_id):
    title = extract_h1(content)
    post = {
        "title": title,
        "content": content,
        "status": "publish",
        "categories": [int(category_id)]
    }
    api_url = url.rstrip('/') + "/wp-json/wp/v2/posts"
    response = requests.post(api_url, auth=HTTPBasicAuth(username, password), json=post)
    response.raise_for_status()
    return response.json().get('link')
