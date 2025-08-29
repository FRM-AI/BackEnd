"""
Data Loader: Tải dữ liệu giá, tài chính, tin tức cho TTCK Việt Nam/Thế giới
"""

import yfinance as yf
import pandas as pd
from vnquant import DataLoader
import requests
import datetime
# from datetime import datetime
from bs4 import BeautifulSoup

def get_company_info_yf(ticker):
    """Lấy thông tin công ty từ Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            'name': info.get('longName', 'N/A'),
            'shortName': info.get('shortName', 'N/A'),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'country': info.get('country', 'N/A')
        }
    except Exception as e:
        print(f"Error getting company info for {ticker}: {e}")
        return None

def load_stock_data_yf(ticker, start=(datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d'), end=datetime.datetime.now().strftime('%Y-%m-%d'), interval='1d'):
    """Tải dữ liệu giá cổ phiếu từ Yahoo Finance"""
    try:
        ticker = ticker.upper() + ".VN"
        df = yf.download(ticker, start=start, end=end, interval=interval)
        # Fix MultiIndex columns issue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns.values]
        df.reset_index(inplace=True)
        return df
    except:
        df = yf.download(ticker, start=start, end=end, interval=interval)
        # Fix MultiIndex columns issue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns.values]
        df.reset_index(inplace=True)
        return df

def load_stock_data_vn(symbol, start='2015-01-01', end=datetime.datetime.now().strftime('%Y-%m-%d')):
    """Tải dữ liệu giá cổ phiếu Việt Nam từ VNQuant (HOSE/HNX/UPCOM)"""
    loader = DataLoader(symbol, start, end)
    df = loader.download()
    df.reset_index(inplace=True)
    df = df.iloc[::-1].reset_index(drop=True)  # Reverse thứ tự
    df['close'] *= 1000
    df['high'] *= 1000
    df['open'] *= 1000
    df['low'] *= 1000
    return df

def load_financials_yf(ticker):
    """Tải báo cáo tài chính từ Yahoo Finance"""
    stock = yf.Ticker(ticker)
    return stock.financials, stock.balance_sheet, stock.cashflow, stock.dividends

# def crawl_news_cafef(symbol, pages=3):
#     """Crawl tin tức từ Cafef cho mã CK (Việt Nam)"""
#     news = []
#     for page in range(1, pages+1):
#         url = f"https://s.cafef.vn/tin-doanh-nghiep/{symbol}/{page}.chn"
#         resp = requests.get(url, timeout=5)
#         if resp.status_code != 200: continue
#         soup = BeautifulSoup(resp.text, 'html.parser')
#         for a in soup.select('.box_tinmoi .tlitem h3 a'):
#             news.append({'title':a.text.strip(),'url':a['href']})
#     return news

# import time
# from requests.exceptions import ReadTimeout, RequestException

# def crawl_news_cafef(symbol, pages=3, retries=3, timeout=10):
#     """Crawl tin tức từ Cafef cho mã CK (Việt Nam)"""
#     news = []
#     symbol = symbol.lower()
#     for page in range(1, pages + 1):
#         url = f"https://cafef.vn/{symbol}/trang-{page}.html"
#         attempt = 0
#         while attempt < retries:
#             try:
#                 resp = requests.get(url, timeout=timeout)
#                 if resp.status_code != 200:
#                     break
#                 soup = BeautifulSoup(resp.text, 'html.parser')
                
#                 # Try different selectors for Cafef news
#                 news_items = soup.select('.box_tinmoi .tlitem') or soup.select('.tlitem')
                
#                 for item in news_items:
#                     try:
#                         # Extract title and link
#                         title_elem = item.select_one('h3 a') or item.select_one('a')
#                         if not title_elem:
#                             continue
                            
#                         title = title_elem.text.strip()
#                         url = title_elem.get('href', '')
                        
#                         # Extract date if available
#                         date_elem = item.select_one('.time') or item.select_one('.date') or item.select_one('.tldate')
#                         date = date_elem.text.strip() if date_elem else datetime.datetime.now().strftime('%Y-%m-%d')
                        
#                         # Extract snippet if available
#                         snippet_elem = item.select_one('.desc') or item.select_one('.summary') or item.select_one('p')
#                         snippet = snippet_elem.text.strip() if snippet_elem else 'Đọc thêm tại Cafef'
                        
#                         news.append({
#                             'title': title, 
#                             'url': url,
#                             'date': date,
#                             'snippet': snippet[:200] + '...' if len(snippet) > 200 else snippet
#                         })
#                     except Exception as e:
#                         print(f"Error parsing Cafef news item: {e}")
#                         continue
#                 break  # Exit retry loop if successful
#             except ReadTimeout:
#                 attempt += 1
#                 print(f"Timeout occurred for {url}. Retrying {attempt}/{retries}...")
#                 time.sleep(2)  # Wait before retrying
#             except RequestException as e:
#                 print(f"Request failed: {e}")
#                 break
#     return news

# def crawl_news_yahoo(ticker, pages=1):
#     """Crawl tin tức từ Yahoo Finance cho mã quốc tế"""
#     try:
#         import requests
#         from bs4 import BeautifulSoup
#         import time
        
#         news = []
#         headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
#         }
        
#         # Try both news URL formats
#         urls = [
#             f"https://finance.yahoo.com/quote/{ticker}/news",
#             f"https://finance.yahoo.com/quote/{ticker}/news/"
#         ]
        
#         for url in urls:
#             try:
#                 resp = requests.get(url, headers=headers, timeout=10)
#                 if resp.status_code == 200:
#                     soup = BeautifulSoup(resp.text, 'html.parser')
                    
#                     # Try different selectors for Yahoo Finance news
#                     selectors = [
#                         'li[class*="js-stream-content"]',
#                         'div[class*="Ov(h)"]',
#                         'div[class*="news-item"]',
#                         'div[class*="StreamItem"]'
#                     ]
                    
#                     for selector in selectors:
#                         items = soup.select(selector)
#                         if items:
#                             for item in items[:pages * 10]:  # Limit results
#                                 try:
#                                     # Extract title
#                                     title_elem = item.find('h3') or item.find('h2') or item.find('a')
#                                     title = title_elem.text.strip() if title_elem else ''
                                    
#                                     # Extract link
#                                     link_elem = item.find('a')
#                                     link = link_elem.get('href', '') if link_elem else ''
                                    
#                                     # Make relative URLs absolute
#                                     if link.startswith('/'):
#                                         link = 'https://finance.yahoo.com' + link
                                    
#                                     # Extract date
#                                     date_elem = (item.find('time') or 
#                                                item.find('span', class_=lambda x: x and 'time' in x.lower()) or
#                                                item.find('div', class_=lambda x: x and 'time' in x.lower()))
                                    
#                                     if date_elem:
#                                         # Try to get datetime attribute first
#                                         date = date_elem.get('datetime', '') or date_elem.text.strip()
#                                         # Clean up date format
#                                         if date and len(date) > 20:
#                                             date = date[:20]  # Truncate long date strings
#                                     else:
#                                         date = datetime.now().strftime('%Y-%m-%d')
                                    
#                                     # Extract snippet/summary
#                                     snippet_elem = item.find('p') or item.find('div', class_='summary')
#                                     snippet = snippet_elem.text.strip() if snippet_elem else 'Read more at Yahoo Finance'
                                    
#                                     if title and len(title) > 10:  # Filter out very short titles
#                                         news.append({
#                                             'title': title,
#                                             'url': link,
#                                             'date': date,
#                                             'snippet': snippet[:200] + '...' if len(snippet) > 200 else snippet,
#                                             'source': 'Yahoo Finance'
#                                         })
                                        
#                                 except Exception as e:
#                                     print(f"Error parsing Yahoo Finance news item: {e}")
#                                     continue
                            
#                             if news:  # If we found news, break
#                                 break
                    
#                     if news:  # If we found news with current URL, break
#                         break
                        
#             except requests.exceptions.RequestException as e:
#                 print(f"Error fetching Yahoo Finance news from {url}: {e}")
#                 continue
        
#         # Remove duplicates based on title
#         unique_news = []
#         seen_titles = set()
#         for article in news:
#             title_lower = article['title'].lower()
#             if title_lower not in seen_titles:
#                 unique_news.append(article)
#                 seen_titles.add(title_lower)
        
#         return unique_news[:20]  # Return top 20 articles
        
#     except Exception as e:
#         print(f"Error in crawl_news_yahoo: {e}")
#         return []

if __name__ == "__main__":
    # print(load_stock_data_yf("MWG.VN"))
    print(load_stock_data_vn("MWG", "2011-01-01"))
    # print(load_financials_yf("VCB.VN")[0][f'{datetime.datetime.now().year - 1}-12-31'])
    # print(crawl_news_cafef("VCB"))
    # print(crawl_news_yahoo("AAPL"))