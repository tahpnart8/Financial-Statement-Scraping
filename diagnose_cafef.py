import requests
from bs4 import BeautifulSoup

def check_ticker(ticker, year):
    url = f"https://s.cafef.vn/bao-cao-tai-chinh/{ticker}/IncSta/{year}/0/0/0/0/bao-cao-ket-qua-hoat-dong-kinh-doanh-.chn"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    header_table = soup.find("table", {"id": "tblGridData"})
    years = []
    if header_table:
        header_row = header_table.find("tr")
        if header_row:
            for td in header_row.find_all("td"):
                text = td.text.strip()
                if text.isdigit() and len(text) == 4:
                    years.append(int(text))
    print(f"--- {ticker} {year} ---")
    print(f"Years found: {years}")
    
    table = soup.find("table", {"id": "tableContent"})
    if table:
        for row in table.find_all("tr")[:1]:
            cols = row.find_all("td")
            for i, c in enumerate(cols):
                style = c.get('style', '')
                if 'width:15%' in style or 'b_r_c' in c.get('class', []):
                    print(f"Col {i} [{style}]: {c.text.strip()}")

check_ticker("VIC", 2017)
check_ticker("HPG", 2017)
