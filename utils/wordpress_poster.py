import requests
from requests.auth import HTTPBasicAuth

def post_to_wordpress(url, username, password, html_content, category_id):
    # Lấy title từ H1 (nếu có)
    import re
    h1_match = re.search(r'<h1.*?>(.*?)</h1>', html_content, re.DOTALL | re.IGNORECASE)
    title = h1_match.group(1).strip() if h1_match else "Bài viết tự động"
    post = {
        "title": title,
        "content": html_content,
        "status": "publish",
        "categories": [int(category_id)]
    }
    api_url = url.rstrip('/') + "/wp-json/wp/v2/posts"
    response = requests.post(api_url, auth=HTTPBasicAuth(username, password), json=post)
    response.raise_for_status()
    return response.json().get('link')
