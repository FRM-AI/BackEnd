"""
Data Loader: Tải dữ liệu giá, tài chính, tin tức cho TTCK Việt Nam/Thế giới
Enhanced with Redis caching for better performance
"""

import yfinance as yf
import pandas as pd
from vnquant import DataLoader
import requests
import datetime
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

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
        # Error getting company info - log internally only
        pass
        return None

def load_stock_data_cached(symbol, asset_type='stock', start=None, end=None, interval='1d'):
    """
    Load stock data with Redis caching support (1-hour TTL)
    Returns cached data if available, otherwise fetches on-demand
    """
    try:
        # Import cache manager here to avoid circular imports
        from stock_cache_manager import get_cache_manager
        
        cache_manager = get_cache_manager()
        symbol = symbol.upper().replace('.VN', '')  # Normalize symbol
        
        # Try to get from cache first
        cached_data = cache_manager.get_stock_data(symbol, asset_type)
        
        if cached_data and cached_data.get('chart_data'):
            logger.info(f"📦 Using cached data for {symbol}")
            
            # Convert chart_data back to DataFrame for analysis functions
            chart_data = cached_data['chart_data']
            
            if chart_data:
                # Create DataFrame from chart data
                df_data = []
                for item in chart_data:
                    df_data.append({
                        'Date': pd.to_datetime(item['time'], unit='s'),
                        'Open': item['open'],
                        'High': item['high'],
                        'Low': item['low'],
                        'Close': item['close'],
                        'Volume': item['volume']
                    })
                
                df = pd.DataFrame(df_data)
                
                # Filter by date range if specified
                if start or end:
                    start_date = pd.to_datetime(start) if start else df['Date'].min()
                    end_date = pd.to_datetime(end) if end else df['Date'].max()
                    df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
                
                return df
            
        # Cache miss - fetch on-demand using updated logic
        logger.warning(f"⚠️ Cache miss for {symbol}, fetching on-demand with VNQuant-first logic")
        return load_stock_data_vnquant(symbol, asset_type, start, end, interval)
            
    except Exception as e:
        logger.error(f"❌ Error in cached stock data loading: {e}")
        # Fallback to original method with VNQuant-first logic
        return load_stock_data_vnquant(symbol, asset_type, start, end, interval)

def get_stock_data_for_api(symbol, asset_type='stock'):
    """
    Get stock data specifically formatted for API response
    Returns the complete API-ready structure from cache or fetches on-demand
    """
    try:
        from stock_cache_manager import get_cache_manager
        
        cache_manager = get_cache_manager()
        symbol = symbol.upper().replace('.VN', '')
        
        # Get cached data or fetch on-demand
        cached_data = cache_manager.get_stock_data(symbol, asset_type)
        
        if cached_data:
            # Add API-specific metadata
            cached_data['authenticated'] = False  # Will be set by API endpoint
            cached_data['generated_at'] = datetime.datetime.now().isoformat()
            cached_data['success'] = True
            cached_data['cache_info'] = 'Retrieved from Redis cache (TTL: 1 hour)'
            
            return cached_data
        
        # If cache manager returns None, it already tried to fetch on-demand
        logger.warning(f"❌ Unable to get data for {symbol} from cache or on-demand fetch")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error getting API-formatted data: {e}")
        return None

def load_stock_data_vnquant(ticker, asset_type='stock', start=(datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d'), end=datetime.datetime.now().strftime('%Y-%m-%d'), interval='1d'):
    """Tải dữ liệu giá cổ phiếu từ VNQuant trước, fallback sang Yahoo Finance"""
    if asset_type == 'stock':
        try:
            # Try VNQuant first for Vietnamese stocks
            logger.info(f"🇻🇳 Trying VNQuant for {ticker}")
            df_vn = load_stock_data_vn(ticker.upper(), start, end)
            
            if not df_vn.empty:
                # Convert VNQuant format to standard format
                df_converted = pd.DataFrame()
                df_converted['Date'] = pd.to_datetime(df_vn['date'])
                df_converted['Open'] = df_vn['open'].astype(float)
                df_converted['High'] = df_vn['high'].astype(float) 
                df_converted['Low'] = df_vn['low'].astype(float)
                df_converted['Close'] = df_vn['close'].astype(float)
                df_converted['Volume'] = df_vn['volume_match'].astype(float)
                
                # Filter by date range
                start_date = pd.to_datetime(start)
                end_date = pd.to_datetime(end)
                df_converted = df_converted[
                    (df_converted['Date'] >= start_date) & 
                    (df_converted['Date'] <= end_date)
                ].reset_index(drop=True)
                
                logger.info(f"✅ Successfully loaded {ticker} data")
                return df_converted
            else:
                raise Exception("No data loaded")
                
        except:
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
    elif asset_type == 'crypto':
        try:
            ticker = ticker.upper() + "-USD"
            df = yf.download(ticker, start=start, end=end, interval=interval)
            # Fix MultiIndex columns issue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns.values]
            df.reset_index(inplace=True)
            
            # Get USD/VND exchange rate for conversion
            try:
                usd_vnd_rate = yf.Ticker("USDVND=X").history(period="1d", interval="1m")["Close"].iloc[-1]
                # Only convert price columns to VND, keep Date and Volume unchanged
                price_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close']
                for col in price_columns:
                    if col in df.columns:
                        df[col] = df[col] * usd_vnd_rate
            except Exception as rate_error:
                # If can't get exchange rate, just return USD values
                print(f"Warning: Could not get USD/VND rate, returning USD values: {rate_error}")
                pass
            
            return df
        except Exception as e:
            # Error loading crypto data - log internally only
            print(f"Error loading crypto data for {ticker}: {e}")
            return None

def load_stock_data_yf(ticker, asset_type='stock', start=(datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d'), end=datetime.datetime.now().strftime('%Y-%m-%d'), interval='1d'):
    """Tải dữ liệu giá cổ phiếu từ Yahoo Finance với fallback sang VNQuant (legacy function)"""
    if asset_type == 'stock': 
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
    elif asset_type == 'crypto':
        try:
            ticker = ticker.upper() + "-USD"
            df = yf.download(ticker, start=start, end=end, interval=interval)
            # Fix MultiIndex columns issue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns.values]
            df.reset_index(inplace=True)
            
            # Get USD/VND exchange rate for conversion
            try:
                usd_vnd_rate = yf.Ticker("USDVND=X").history(period="1d", interval="1m")["Close"].iloc[-1]
                # Only convert price columns to VND, keep Date and Volume unchanged
                price_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close']
                for col in price_columns:
                    if col in df.columns:
                        df[col] = df[col] * usd_vnd_rate
            except Exception as rate_error:
                # If can't get exchange rate, just return USD values
                print(f"Warning: Could not get USD/VND rate, returning USD values: {rate_error}")
                pass
            
            return df
        except Exception as e:
            # Error loading crypto data - log internally only
            print(f"Error loading crypto data for {ticker}: {e}")
            return None

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

    # Kiểm tra và xóa dòng cuối cùng nếu giá trị 'close' không hợp lệ
    if df['close'].iloc[-1] == 0 or pd.isna(df['close'].iloc[-1]):
        df = df.iloc[:-1]  # Xóa dòng cuối cùng
        
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
    # Test with cached data loading
    # print("Testing cached data loading...")
    # print(load_stock_data_cached("VCB", "stock"))
    # Test the new VNQuant-first function
    print("Testing VNQuant-first loading...")
    print(load_stock_data_vnquant("VCB"))
    
    # print("Testing original YF loading...")
    print(load_stock_data_yf("VCB"))
    # print(load_stock_data_vn("VCB", "2011-01-01"))
    # print(load_financials_yf("VCB")[0][f'{datetime.datetime.now().year - 1}-12-31'])
    # print(crawl_news_cafef("VCB"))
    # print(crawl_news_yahoo("AAPL"))