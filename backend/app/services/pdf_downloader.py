import logging
import os
import requests
import tempfile
import urllib.parse
from bs4 import BeautifulSoup
from typing import Optional

logger = logging.getLogger(__name__)

def search_cafef_pdf(ticker: str, year: int) -> Optional[str]:
    """
    Search CafeF for the Audited Financial Statement PDF for a specific year.
    """
    logger.info(f"Searching CafeF for {ticker} BCTC {year}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"https://s.cafef.vn/hoso/congty/{ticker}/tai-lieu-bao-cao.chn"
    }
    
    # Try searching the Events/News API
    url = f"https://s.cafef.vn/Ajax/Events_RelatedNews_New.aspx?symbol={ticker}&floorID=0&configID=0&PageIndex=1&PageSize=50"
    
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.find_all("a")
        
        for link in links:
            title = link.text.strip().upper()
            href = link.get("href", "")
            
            if str(year) in title and ("KIỂM TOÁN" in title or "BCTC" in title or "BÁO CÁO TÀI CHÍNH" in title):
                # Found a potential link. CafeF often redirects these to a PDF or a detail page.
                if "cafef.vn" not in href and href.startswith("/"):
                    href = "https://s.cafef.vn" + href
                
                # Some links are just details containing the actual PDF download.
                # E.g. https://s.cafef.vn/Luu-tru-tai-lieu.chn?id=...
                # For this implementation, we assume the href leads to a PDF or a page with the PDF.
                # To be perfectly accurate, we might need to follow the link.
                logger.info(f"Found potential document link for {ticker} {year}: {href}")
                return href
                
    except Exception as e:
        logger.error(f"Error searching CafeF PDF: {e}")
        
    return None

def get_bctc_pdf_url(ticker: str, year: int) -> Optional[str]:
    """
    Returns the PDF URL. Currently attempts CafeF.
    """
    return search_cafef_pdf(ticker, year)

def download_pdf(url: str, ticker: str, year: int) -> Optional[str]:
    """
    Downloads a PDF from a given URL to the /tmp directory.
    Uses caching: if the file already exists, it returns it immediately.
    Returns the local file path.
    """
    if not url:
        return None
        
    tmp_dir = "/tmp/bctc_pdfs"
    os.makedirs(tmp_dir, exist_ok=True)
    file_path = os.path.join(tmp_dir, f"{ticker}_{year}_BCTC.pdf")
    
    # Check cache first
    if os.path.exists(file_path):
        logger.info(f"Using cached PDF for {ticker} {year}: {file_path}")
        return file_path
        
    logger.info(f"Downloading PDF for {ticker} {year} from {url}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # If it's a cafef doc link, we can just GET it. Cloudflare might block it.
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
        
        if resp.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            logger.info(f"PDF successfully downloaded to {file_path}")
            return file_path
        else:
            logger.error(f"Failed to download PDF. Status code: {resp.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error downloading PDF: {e}")
        return None
