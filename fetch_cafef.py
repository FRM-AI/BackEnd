import pandas as pd
from pyparsing import col
import requests
from datetime import datetime, timezone
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import random
import json

# Proxy list (thay thế bằng proxy của bạn nếu cần)
# PROXIES = [
#     "http://proxy1:port",
#     "http://proxy2:port",
#     "http://proxy3:port"
# ]

# Headers để giả lập trình duyệt
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive"
}

def get_data(url, params=None):
    """
    Hàm chung để gửi yêu cầu GET với proxy và headers.
    """
    # proxy = {"http": random.choice(PROXIES), "https": random.choice(PROXIES)}
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10, verify=False)
        response.raise_for_status()
        # Check if the response is JSON
        if 'application/json' in response.headers.get('Content-Type', ''):
            return response.json()
        else:
            # Return raw text for non-JSON responses
            return response.text
    except requests.exceptions.RequestException as e:
        print(e)
        return None

def convert_date(date_str):
    """
    Chuyển đổi giá trị /Date(1759770000000)/ thành định dạng ngày tháng.
    """
    try:
        # Trích xuất số từ chuỗi /Date(1759770000000)/
        timestamp = int(date_str.strip('/Date()/'))
        # Chuyển đổi từ mili-giây sang giây và định dạng thành ngày tháng với múi giờ UTC
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        return None  # Trả về None nếu không thể chuyển đổi

# API 1: Lấy dữ liệu giao dịch cổ đông
def get_shareholder_data(symbol, start_date, end_date, page_index, page_size):
    url = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx"
    params = {
        "Symbol": symbol,
        "StartDate": start_date,
        "EndDate": end_date,
        "PageIndex": page_index,
        "PageSize": page_size
    }
    response = get_data(url, params)

    try:
        data = response if isinstance(response, dict) else json.loads(response)
        return data.get("Data", {}).get("Data", [])  # Trả về danh sách dữ liệu
    except Exception as e:
        print(f"Lỗi khi xử lý dữ liệu: {e}")
        return []

# API 2: Lấy lịch sử giá
def get_price_history(symbol, start_date, end_date, page_index, page_size):
    url = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx"
    params = {
        "Symbol": symbol,
        "StartDate": start_date,
        "EndDate": end_date,
        "PageIndex": page_index,
        "PageSize": page_size
    }
    return get_data(url, params)

# API 3: Lấy dữ liệu giao dịch khối ngoại
def get_foreign_trading_data(symbol, start_date, end_date, page_index, page_size):
    url = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDKhoiNgoai.ashx"
    params = {
        "Symbol": symbol,
        "StartDate": start_date,
        "EndDate": end_date,
        "PageIndex": page_index,
        "PageSize": page_size
    }
    response = get_data(url, params)
    try:
        data = response if isinstance(response, dict) else json.loads(response)
        return data.get("Data", {}).get("Data", [])  # Trả về danh sách dữ liệu
    except Exception as e:
        print(f"Lỗi khi xử lý dữ liệu: {e}")
        return []


# API 4: Lấy dữ liệu giao dịch tự doanh
def get_proprietary_trading_data(symbol, start_date, end_date, page_index, page_size):
    url = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDTuDoanh.ashx"
    params = {
        "Symbol": symbol,
        "StartDate": start_date,
        "EndDate": end_date,
        "PageIndex": page_index,
        "PageSize": page_size
    }
    response = get_data(url, params)
    try:
        data = response if isinstance(response, dict) else json.loads(response)
        return data.get("Data", {}).get("Data", [])  # Trả về danh sách dữ liệu
    except Exception as e:
        print(f"Lỗi khi xử lý dữ liệu: {e}")
        return []

# API 5: Lấy giá khớp lệnh theo ngày
def get_match_price(symbol, date):
    # Chuẩn hoá định dạng ngày từ 'YYYY-MM-DD' sang 'YYYYMMDD'
    date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y%m%d")
    
    url = "https://msh-appdata.cafef.vn/rest-api/api/v1/MatchPrice"
    params = {
        "symbol": symbol,
        "date": date # Định dạng 'YYYYMMDD' = '20251014'
    }
    return get_data(url, params)

# API 6: Lấy giá realtime
def get_realtime_price(symbol):
    url = f"https://msh-appdata.cafef.vn/rest-api/api/v1/Watchlists/{symbol}/price"
    return get_data(url)

# API 7: Lấy thông tin công ty
def get_company_info(symbol):
    url = "https://cafef.vn/du-lieu/Ajax/CongTy/ThongTinChung.aspx"
    params = {"sym": symbol}
    return get_data(url, params)

# API 8: Lấy danh sách ban lãnh đạo
def get_leadership(symbol):
    url = "https://cafef.vn/du-lieu/Ajax/CongTy/BanLanhDao.aspx"
    params = {"sym": symbol}
    return get_data(url, params)

# API 9: Lấy danh sách công ty con
def get_subsidiaries(symbol):
    url = "https://cafef.vn/du-lieu/Ajax/CongTy/CongTyCon.aspx"
    params = {"sym": symbol}
    return get_data(url, params)

# API 10: Lấy báo cáo tài chính
def get_financial_reports(symbol):
    url = "https://cafef.vn/du-lieu/Ajax/CongTy/BaoCaoTaiChinh.aspx"
    params = {"sym": symbol}
    return get_data(url, params)

# API 11: Lấy hồ sơ công ty
def get_company_profile(symbol, type_id, page_index, page_size):
    url = "https://cafef.vn/du-lieu/Ajax/HoSoCongTy.aspx"
    params = {
        "symbol": symbol,
        "Type": type_id,
        "PageIndex": page_index,
        "PageSize": page_size
    }
    return get_data(url, params)

# API 12: Lấy dữ liệu tài chính

def get_finance_data(symbol):
    url = "https://cafef.vn/du-lieu/Ajax/PageNew/FinanceData/fi.ashx"
    params = {"symbol": symbol}
    return get_data(url, params)

# API 13: Lấy chỉ số thế giới

def get_global_indices():
    url = "https://cafef.vn/du-lieu/ajax/mobile/smart/ajaxchisothegioi.ashx"
    response = get_data(url)
    try:
        # Parse response to JSON if it's a string
        data = response if isinstance(response, dict) else json.loads(response)
        return data["Data"]
    except json.JSONDecodeError as e:
        print(f"Lỗi khi phân tích cú pháp JSON: {e}")
        return None

if __name__ == "__main__":
    # Test API 1: Lấy dữ liệu giao dịch cổ đông
    # print("Testing get_shareholder_data...")
    # GDCoDong = get_shareholder_data("VIC", None, None, 1, 14)

    # # Test API 2: Lấy lịch sử giá
    # print("Testing get_price_history...")
    # print(get_price_history("VIC", None, None, 1, 14))

    # Test API 3: Lấy dữ liệu giao dịch khối ngoại
    # print("Testing get_foreign_trading_data...")
    # print(get_foreign_trading_data("VIC", None, None, 1, 14))

    # # Test API 4: Lấy dữ liệu giao dịch tự doanh
    # print("Testing get_proprietary_trading_data...")
    # print(pd.DataFrame(get_proprietary_trading_data("VIC", None, None, 1, 14)["ListDataTudoanh"]))

    # # Test API 5: Lấy giá khớp lệnh theo ngày
    # print("Testing get_match_price...")
    # Giả sử GiaKhopLenh là một DataFrame
    # GiaKhopLenh = get_match_price("VIC", "20251014")['data']

    # # Test API 6: Lấy giá realtime
    # print("Testing get_realtime_price...")
    # print(get_realtime_price("VIC"))

    # Test API 7: Lấy thông tin công ty
    # print("Testing get_company_info...")
    # print(get_company_info("VIC"))

    # # Test API 8: Lấy danh sách ban lãnh đạo
    # print("Testing get_leadership...")
    # print(get_leadership("VIC"))

    # # Test API 9: Lấy danh sách công ty con
    # print("Testing get_subsidiaries...")
    # print(get_subsidiaries("VIC"))

    # # Test API 10: Lấy báo cáo tài chính
    # print("Testing get_financial_reports...")
    # print(get_financial_reports("VIC"))

    # # Test API 11: Lấy hồ sơ công ty
    # print("Testing get_company_profile...")
    # print(get_company_profile("VIC", 1, 0, 4))

    # Test API 12: Lấy dữ liệu tài chính
    # print("Testing get_finance_data...")
    # print(get_finance_data("VIC"))

    # Test API 13: Lấy chỉ số thế giới
    print("Testing get_global_indices...")
    print(get_global_indices())