import requests
from bs4 import BeautifulSoup

def inspect_cafef_html(ticker="DMC", year=2017):
    url = f"https://s.cafef.vn/bao-cao-tai-chinh/{ticker}/IncSta/{year}/0/0/0/0/bao-cao-ket-qua-hoat-dong-kinh-doanh-.chn"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    content_table = soup.find("table", {"id": "tableContent"})
    if content_table:
        rows = content_table.find_all("tr")
        for row in rows[:1]:
            cols = row.find_all("td")
            for i, col in enumerate(cols):
                print(f"Col {i}: text='{col.text.strip()}' class='{col.get('class', [])}' style='{col.get('style', '')}' width='{col.get('width', '')}'")

inspect_cafef_html("DMC", 2017)
