import requests
from bs4 import BeautifulSoup

def search():
    ticker = "DMC"
    headers = {"User-Agent": "Mozilla/5.0"}
    for page in range(1, 10):
        url = f"https://s.cafef.vn/Ajax/Events_RelatedNews_New.aspx?symbol={ticker}&floorID=0&configID=0&PageIndex={page}&PageSize=50"
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a"):
            title = a.text.upper()
            if "BCTC" in title or "BÁO CÁO TÀI CHÍNH" in title or "BÁO CÁO KIỂM TOÁN" in title:
                print(f"Page {page}: {a.text} | {a.get('href')}")

search()
