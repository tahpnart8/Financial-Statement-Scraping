import requests

def search_vndirect(ticker="DMC"):
    url = f"https://finfo-api.vndirect.com.vn/v4/news?q=symbols:{ticker}~type:DISCLOSURE&size=20&page=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    print(resp.status_code)
    if resp.status_code == 200:
        data = resp.json().get('data', [])
        for item in data:
            print(item.get('title'), item.get('documentUrl'))

search_vndirect()