import requests
from requests.auth import HTTPBasicAuth

def post_to_wordpress(url, username, password, html_content, category_id, title, featured_media_id=None):
    post = {
        "title": title,
        "content": html_content,
        "status": "publish",
        "categories": [int(category_id)]
    }
    if featured_media_id:
        post["featured_media"] = featured_media_id
    api_url = url.rstrip('/') + "/wp-json/wp/v2/posts"
    response = requests.post(api_url, auth=HTTPBasicAuth(username, password), json=post)
    response.raise_for_status()
    return response.json().get('link')
