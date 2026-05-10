import asyncio
import os
import sys
import io

# Set UTF-8 encoding for standard output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.services.data_fetcher import fetch_all_reports
from app.services.data_mapper import map_financial_data
from app.services.excel_writer import generate_excel

def test_fetch_and_generate():
    ticker = "DMC"
    period = "year"
    year_from = 2015
    year_to = 2015
    output_dir = "./test_output"

    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    try:
        # Fetch
        print("Fetching data...")
        reports = fetch_all_reports(ticker, period, year_from, year_to)
        print("Fetched reports:", reports.keys())
        
        # Map
        print("Mapping data...")
        mapped = map_financial_data(reports, year_from, year_to)
        print("Mapped data sections:", mapped.keys())
        
        # Verify years in mapped data
        if "income_statement" in mapped and "revenue" in mapped["income_statement"]:
            years = sorted(mapped["income_statement"]["revenue"].keys())
            print(f"Successfully mapped revenue for years: {years}")
        
        # Generate Excel
        print("Generating Excel...")
        filepath = generate_excel(ticker, mapped, year_from, year_to, output_dir)
        print(f"Success! Excel file generated at: {filepath}")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fetch_and_generate()
