import requests
from bs4 import BeautifulSoup
import pandas as pd

def parse_cafef(ticker="DMC", year=2017):
    url = f"https://s.cafef.vn/bao-cao-tai-chinh/{ticker}/IncSta/{year}/0/0/0/0/bao-cao-ket-qua-hoat-dong-kinh-doanh-.chn"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    header_table = soup.find("table", {"id": "tblGridData"})
    years = []
    if header_table:
        header_row = header_table.find("tr")
        if header_row:
            tds = header_row.find_all("td")
            for td in tds:
                text = td.text.strip()
                if text.isdigit() and len(text) == 4:
                    years.append(int(text))
    print(f"Extracted years: {years}")
    
    content_table = soup.find("table", {"id": "tableContent"})
    if content_table:
        rows = content_table.find_all("tr")
        for row in rows[:2]:
            cols = row.find_all("td")
            texts = [c.text.strip() for c in cols]
            print(texts)

parse_cafef("DMC", 2014)
