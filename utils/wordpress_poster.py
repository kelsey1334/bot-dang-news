import requests
from requests.auth import HTTPBasicAuth

def post_to_wordpress(url, username, password, content, category):
    # Giả sử bài viết chuẩn markdown, bạn cần convert markdown -> HTML nếu WordPress dùng classic editor
    post = {
        "title": "Tự động đăng bài (SEO Bot)",
        "content": content,
        "status": "publish",
        "categories": [category]  # ID hoặc slug
    }
    api_url = url.rstrip('/') + "/wp-json/wp/v2/posts"
    response = requests.post(api_url, auth=HTTPBasicAuth(username, password), json=post)
    response.raise_for_status()
    return response.json().get('link')
