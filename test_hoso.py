import requests
from bs4 import BeautifulSoup

def test_hoso_page(ticker="DMC"):
    print(f"--- Testing Ho So page for {ticker} ---")
    url = f"https://s.cafef.vn/hoso/{ticker}/tai-lieu-bao-cao.chn"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Find all links that might be PDFs
            links = soup.find_all("a", href=True)
            count = 0
            for link in links:
                href = link['href']
                title = link.text.strip().upper()
                if "BCTC" in title or "KIỂM TOÁN" in title or ".PDF" in href.upper():
                    print(f"Found: {title} | Link: {href}")
                    count += 1
            print(f"Total potential links: {count}")
        else:
            print(f"Blocked or Error: {resp.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

test_hoso_page("DMC")
