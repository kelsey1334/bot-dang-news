import pandas as pd

def parse_excel(path):
    xl = pd.ExcelFile(path)
    accounts = xl.parse('tai_khoan')
    posts = xl.parse('key_word')
    return accounts, posts
