import requests
import json

def test_dnse(ticker="DMC"):
    # Try DNSE API
    print("--- Testing DNSE ---")
    url = f"https://services.entrade.com.vn/chart-api/v2/finance/income?symbol={ticker}"
    try:
        resp = requests.get(url, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(resp.json())
    except Exception as e:
        print(f"Error: {e}")

def test_fpts(ticker="DMC"):
    print("\n--- Testing FPTS ---")
    url = f"https://ezsearch.fpts.com.vn/Services/EzData/BaoCaoTaiChinh.aspx?s={ticker}"
    try:
        resp = requests.get(url, timeout=10)
        print(f"Status: {resp.status_code}")
        with open("fpts.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("Saved to fpts.html")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_dnse()
    test_fpts()
