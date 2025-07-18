import requests
from requests.structures import CaseInsensitiveDict
import os

SINBYTE_APIKEY = os.getenv('SINBYTE_APIKEY')
SINBYTE_NAME = os.getenv('SINBYTE_NAME', 'Auto Index')
SINBYTE_DRIPFEED = int(os.getenv('SINBYTE_DRIPFEED', 1))

def ping_sinbyte(urls):
    """
    Gửi 1 hoặc nhiều url lên Sinbyte API để ép index.
    :param urls: list các url (hoặc 1 url string)
    :return: (True, resp.text) nếu thành công, (False, resp.text) nếu lỗi
    """
    if SINBYTE_APIKEY is None:
        return False, "SINBYTE_APIKEY not set in environment variables!"
    if isinstance(urls, str):
        urls = [urls]
    url = "https://app.sinbyte.com/api/indexing/"
    headers = CaseInsensitiveDict()
    headers["Authorization"] = "{'Content-Type': 'application/json'}"
    headers["Content-Type"] = "application/json"
    data = {
        "apikey": SINBYTE_APIKEY,
        "name": SINBYTE_NAME,
        "dripfeed": SINBYTE_DRIPFEED,
        "urls": urls
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            return True, resp.text
        else:
            return False, f"Status: {resp.status_code} - {resp.text}"
    except Exception as e:
        return False, str(e)
