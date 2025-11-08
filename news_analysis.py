import google.generativeai as genai
# Configure the API key
genai.configure(api_key='AIzaSyDYZrQbhP6fc0LHdM1XkESfoCcnUv92jFY')

from data_loader import load_stock_data_vnquant, load_stock_data_yf, load_stock_data_vn
from feature_engineering import *
from technical_analysis import *
from fetch_cafef import *

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import time
import random
from typing import List
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_result,
)

import asyncio
import json
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor

async def generate_with_heartbeat(model, prompt, section_name="analysis"):
    """
    Chạy model.generate_content với heartbeat thực sự hiệu quả và streaming hoàn chỉnh
    """
    result_queue = asyncio.Queue()
    error_queue = asyncio.Queue()
    generation_started = asyncio.Event()
    generation_completed = asyncio.Event()
    
    def split_text_into_chunks(text, chunk_size=50):
        """Chia text thành các chunks nhỏ hơn để tạo hiệu ứng streaming"""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            chunks.append(chunk)
        return chunks
    
    # Async function để chạy generation
    async def run_generation():
        try:
            generation_started.set()
            
            # Chạy sync function trong thread pool
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                response = await loop.run_in_executor(
                    executor, 
                    lambda: model.generate_content([prompt], stream=True)
                )
            
            # Stream từng chunk từ Gemini
            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    # Nếu chunk quá lớn, chia nhỏ thêm
                    if len(chunk.text.split()) > 50:
                        sub_chunks = split_text_into_chunks(chunk.text, 30)
                        for sub_chunk in sub_chunks:
                            await result_queue.put(('content', sub_chunk))
                            await asyncio.sleep(0.15)
                    else:
                        await result_queue.put(('content', chunk.text))
                        await asyncio.sleep(0.2)
            
            await result_queue.put(('complete', None))
            generation_completed.set()
            
        except Exception as e:
            await error_queue.put(('error', str(e)))
            generation_completed.set()
    
    # Async function để gửi heartbeat và xử lý kết quả
    async def process_results():
        heartbeat_count = 0
        last_heartbeat = time.time()
        heartbeat_interval = 3  # Gửi heartbeat mỗi 3 giây
        
        while not generation_completed.is_set():
            try:
                # Kiểm tra nếu có lỗi
                try:
                    error_type, error_msg = error_queue.get_nowait()
                    yield f"data: {json.dumps({'type': 'error', 'section': section_name, 'message': f'Lỗi: {error_msg}'})}\n\n"
                    return
                except asyncio.QueueEmpty:
                    pass
                
                # Xử lý kết quả từ generation
                content_processed = False
                try:
                    while True:
                        result_type, content = result_queue.get_nowait()
                        content_processed = True
                        
                        if result_type == 'content':
                            yield f"data: {json.dumps({'type': 'content', 'section': section_name, 'text': content})}\n\n"
                        elif result_type == 'complete':
                            return  # Generation hoàn tất
                            
                except asyncio.QueueEmpty:
                    pass
                
                # Gửi heartbeat nếu không có content và đã đủ thời gian
                current_time = time.time()
                if not content_processed and generation_started.is_set() and (current_time - last_heartbeat) >= heartbeat_interval:
                    heartbeat_count += 1
                    yield f"data: {json.dumps({'type': 'status', 'message': f'🤖 Đang xử lý {section_name}... ({heartbeat_count})', 'progress': 0, 'heartbeat': True})}\n\n"
                    last_heartbeat = current_time
                
                # Chờ ngắn trước khi kiểm tra lại
                await asyncio.sleep(0.1)
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'section': section_name, 'message': f'Lỗi xử lý: {str(e)}'})}\n\n"
                return
    
    try:
        # Bắt đầu generation task
        generation_task = asyncio.create_task(run_generation())
        
        # Xử lý kết quả và heartbeat
        async for chunk in process_results():
            yield chunk
        
        # Đảm bảo generation task hoàn thành
        await generation_task
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'section': section_name, 'message': f'Lỗi: {str(e)}'})}\n\n"

def check_rate_limit_status(response):
    """Determine if response shows rate limiting (HTTP 429)"""
    return response.status_code == 429

@retry(
    retry=(retry_if_result(check_rate_limit_status)),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
)
def execute_request(url, headers):
    """Execute HTTP request with retry mechanism for rate limits"""
    # Add random delay to avoid being flagged
    time.sleep(random.uniform(2, 6))
    response = requests.get(url, headers=headers)
    return response

async def get_advice_streaming(symbol, signals, user_info):
    try:
        yield f"data: {json.dumps({'type': 'status', 'message': 'Cho khuyến nghị đầu tư...', 'progress': 10})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'advice', 'title': 'Khuyến nghị đầu tư'})}\n\n"

        # Tạo prompt cho phân tích
        prompt = f"""
            Bạn là chuyên gia đầu tư lướt sóng (short-term trader) chuyên nghiệp, có khả năng đọc hiểu dữ liệu kỹ thuật, dòng tiền, và tâm lý thị trường.

            Phân tích chuyên sâu mã cổ phiếu **{symbol}** dựa trên dữ liệu sau:
            {signals}

            Người dùng **đã mua cổ phiếu ở mức giá: {user_info} (giá trị None khi người dùng chưa mua)**  
            Đây là yếu tố **cực kỳ quan trọng**, phải được sử dụng làm **trung tâm phân tích**.

            Hãy:
            1. So sánh giá mua của người dùng với các ngưỡng kỹ thuật, vùng hỗ trợ/kháng cự, tín hiệu xu hướng trong dữ liệu.
            2. Dự đoán hướng giá ngắn hạn (1–2 tuần tới).
            3. Đưa ra **hành động đầu tư cụ thể cho người dùng này**, KHÔNG phải cho nhà đầu tư chung chung:
            - **Kết luận rõ ràng:** MUA / GIỮ / BÁN
            - **Chi tiết kế hoạch hành động cá nhân hoá:**
                - Nếu đang lãi: đề xuất **mức chốt lời cụ thể (TP)** theo giá.
                - Nếu đang lỗ: đề xuất **mức cắt lỗ cụ thể (SL)**, và lý do nên giữ hoặc thoát vị thế.
            4. Dựa trên tín hiệu {symbol} và **mức giá mua {user_info}**, hãy điều chỉnh khuyến nghị sao cho người dùng có thể **tối ưu lợi nhuận ngắn hạn và hạn chế rủi ro**.
            5. Trình bày ngắn gọn, rõ ràng, theo dạng gạch đầu dòng:
            - Phân tích ngắn hạn
            - Mức giá quan trọng (hỗ trợ / kháng cự)
            - Kết luận hành động (MUA / GIỮ / BÁN)
            - Mức CHỐT LỜI (Take Profit)
            - Mức CẮT LỖ (Stop Loss)
            - Nhận định rủi ro kèm lời khuyên cụ thể cho **người đã mua ở mức giá {user_info}**

            Không thêm lời chào, lời kết, hoặc diễn giải lại yêu cầu.
            """

        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích khuyến nghị đầu tư...', 'progress': 50})}\n\n"

        # Bước 3: Gọi mô hình Generative AI
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="advice"):
                yield chunk
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'section': 'advice', 'message': 'Lỗi trong quá trình phân tích'})}\n\n"

        yield f"data: {json.dumps({'type': 'section_end', 'section': 'advice'})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích giao dịch tự doanh hoàn tất!', 'progress': 100})}\n\n"
        
    except Exception:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống trong phân tích giao dịch tự doanh'})}\n\n"

def extractNewsData(search_term, date_start, date_end):
    """
    Extract search results for specified query and date range.
    search_term: str - the search query
    date_start: str - beginning date in yyyy-mm-dd or mm/dd/yyyy format
    date_end: str - ending date in yyyy-mm-dd or mm/dd/yyyy format
    """
    if "-" in date_start:
        date_start = datetime.strptime(date_start, "%Y-%m-%d")
        date_start = date_start.strftime("%m/%d/%Y")
    if "-" in date_end:
        date_end = datetime.strptime(date_end, "%Y-%m-%d")
        date_end = date_end.strftime("%m/%d/%Y")

    request_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/101.0.4951.54 Safari/537.36"
        )
    }

    collected_news = []
    current_page = 0
    while True:
        page_offset = current_page * 10
        search_url = (
            f"https://www.google.com/search?q={search_term}"
            f"&tbs=cdr:1,cd_min:{date_start},cd_max:{date_end}"
            f"&tbm=nws&start={page_offset}"
        )

        try:
            response = execute_request(search_url, request_headers)
            parser = BeautifulSoup(response.content, "html.parser")
            page_results = parser.select("div.SoaBEf")

            if not page_results:
                break  # No additional results available

            for element in page_results:
                try:
                    article_link = element.find("a")["href"]
                    article_title = element.select_one("div.MBeuO").get_text()
                    article_snippet = element.select_one(".GI74Re").get_text()
                    article_date = element.select_one(".LfVVr").get_text()
                    article_source = element.select_one(".NUnG9d span").get_text()
                    collected_news.append(
                        {
                            "link": article_link,
                            "title": article_title,
                            "snippet": article_snippet,
                            "date": article_date,
                            "source": article_source,
                        }
                    )
                except Exception as error:
                    # Error processing result - log internally only
                    pass
                    # Skip this result if any field is missing
                    continue

            # Look for pagination "Next" button
            pagination_next = parser.find("a", id="pnnext")
            if not pagination_next:
                break

            current_page += 1

        except Exception as error:
            # Failed after multiple retries - log internally only
            pass
            break

    return collected_news

def fetch_google_news(
    search_query: str,
    current_date: str,
    days_back: int,
) -> str:
    """
    Fetch with query, current date, and lookback period
    search_query: Query string to search
    current_date: Current date in yyyy-mm-dd format
    days_back: Number of days to look back
    """
    formatted_query = search_query.replace(" ", "+")

    date_current = datetime.strptime(current_date, "%Y-%m-%d")
    date_previous = date_current - relativedelta(days=days_back)
    date_previous = date_previous.strftime("%Y-%m-%d")

    news_data = extractNewsData(formatted_query, date_previous, current_date)

    news_content = ""

    for article in news_data:
        news_content += (
            f"### {article['title']} (source: {article['source']}, date: {article['date']}, link: {article['link']}) \n\n{article['snippet']}\n\n"
        )

    if len(news_data) == 0:
        return ""

    return f"## {search_query}, from {date_previous} to {current_date}:\n\n{news_content}"

async def get_intraday_match_analysis_streaming(symbol: str, date: str):
    """
    Streaming version of get_intraday_match_analysis.
    Args:
        symbol (str): Stock symbol.
        date (str): Date in 'YYYY-MM-DD' format.
    Yields:
        str: Server-Sent Events formatted data.
    """
    try:
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tạo phân tích khớp lệnh trong phiên..', 'progress': 0})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'intraday_analysis', 'title': 'Phân Tích Khớp Lệnh Trong Phiên'})}\n\n"

        # Bước 1: Lấy dữ liệu khớp lệnh
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải dữ liệu khớp lệnh trong phiên...', 'progress': 10})}\n\n"
        
        try:
            match_data = get_match_price(symbol=symbol, date=date)
            GiaKhopLenh = pd.DataFrame(match_data['data'])
            aggregates = pd.DataFrame(match_data['aggregates'])
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi khi lấy dữ liệu khớp lệnh: {str(e)}'})}\n\n"
            return

        # Nếu số dòng ít hơn 20, lấy toàn bộ
        if len(GiaKhopLenh) <= 20:
            GiaKhopLenh_reduced = GiaKhopLenh.reset_index(drop=True)
        elif len(GiaKhopLenh) <= 100:
            # Lấy các điểm cách nhau 5 dòng
            GiaKhopLenh_reduced = pd.concat([GiaKhopLenh.iloc[::5], GiaKhopLenh.iloc[[-1]]]).reset_index(drop=True)
        elif len(GiaKhopLenh) <= 500:
            # Lấy các điểm cách nhau 15 dòng
            GiaKhopLenh_reduced = pd.concat([GiaKhopLenh.iloc[::15], GiaKhopLenh.iloc[[-1]]]).reset_index(drop=True)
        elif len(GiaKhopLenh) <= 1000:
            # Lấy các điểm cách nhau 30 dòng
            GiaKhopLenh_reduced = pd.concat([GiaKhopLenh.iloc[::30], GiaKhopLenh.iloc[[-1]]]).reset_index(drop=True)
        elif len(GiaKhopLenh) <= 5000:
            # Lấy các điểm cách nhau 100 dòng và đảm bảo dòng cuối cùng luôn được bao gồm
            GiaKhopLenh_reduced = pd.concat([GiaKhopLenh.iloc[::100], GiaKhopLenh.iloc[[-1]]]).reset_index(drop=True)
        elif len(GiaKhopLenh) <= 10000:
            # Lấy các điểm cách nhau 150 dòng và đảm bảo dòng cuối cùng luôn được bao gồm
            GiaKhopLenh_reduced = pd.concat([GiaKhopLenh.iloc[::150], GiaKhopLenh.iloc[[-1]]]).reset_index(drop=True)
        else:
            # Lấy các điểm cách nhau 200 dòng và đảm bảo dòng cuối cùng luôn được bao gồm
            GiaKhopLenh_reduced = pd.concat([GiaKhopLenh.iloc[::200], GiaKhopLenh.iloc[[-1]]]).reset_index(drop=True)
            
        GiaKhopLenh_reduced['volume'] *= 100
        GiaKhopLenh_reduced['totalVolume'] *= 100
        GiaKhopLenh_reduced.drop(columns=['totalValue', 'totalVolume'], inplace=True)

        schema = {
            "symbol": "Mã cổ phiếu",
            "time": "Thời điểm khớp lệnh cụ thể (giờ giao dịch trong ngày) (YY-MM-DDTHH:MM:SS)",
            "basicPrice": "Giá cơ sở (nghìn đồng)",
            "price": "Giá khớp lệnh (nghìn đồng)",
            "volume": "Khối lượng khớp lệnh (cổ phiếu)"
        }

        schema_aggregates = {
            "price": "Giá khớp lệnh (nghìn đồng)",
            "totalVolume": "Tổng khối lượng khớp lệnh (cổ phiếu)",
            "volPercent": "Tỷ lệ khối lượng khớp lệnh tại giá này so với tổng khối lượng khớp lệnh (%)"
        }

        data_json = GiaKhopLenh_reduced.to_json(orient="records", force_ascii=False)
        GiaKhopLenh_pretty = json.dumps({
            "schema": schema,
            "records": json.loads(data_json)
        }, indent=2, ensure_ascii=False)

        data_aggregates_json = aggregates.to_json(orient="records", force_ascii=False)
        aggregates_pretty = json.dumps({
            "schema": schema_aggregates,
            "records": json.loads(data_aggregates_json)
        }, indent=2, ensure_ascii=False)

        yield f"data: {json.dumps({'type': 'status', 'message': 'Dữ liệu khớp lệnh đã sẵn sàng...', 'progress': 30})}\n\n"
        
        # Bước 2: Tạo prompt cho phân tích
        prompt = f"""
        Bạn là chuyên gia phân tích tài chính chuyên nghiệp. 
        Hãy đánh giá chi tiết và chính xác mã cổ phiếu dựa trên dữ liệu giá khớp lệnh theo ngày dưới đây. 
        Đưa ra các nhận định chuyên môn, giả thuyết hợp lý có cơ sở.

        Dữ liệu:
        {GiaKhopLenh_pretty}

        Tổng hợp:
        {aggregates_pretty}

        Yêu cầu:
        - Trả lời cực kì KHÁCH QUAN mang tính chuyên môn cao.
        - Đọc hiểu số liệu đã cung cấp thật chuyên sâu.
        - Phân tích lực cầu/lực cung trong phiên.
        - Đánh giá xu hướng giá, thanh khoản và biến động.
        - Đưa ra nhận định về khả năng xu hướng ngắn hạn.
        - Đưa ra giả thuyết hợp lý, sáng tạo, có chiều sâu.
        - Không giải thích lại yêu cầu, không thêm lời mở đầu hoặc kết luận ngoài phân tích chính.
        """

        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích dữ liệu...', 'progress': 50})}\n\n"

        # Bước 3: Sử dụng async generator với heartbeat
        model = genai.GenerativeModel('gemini-2.5-flash')
        async for chunk in generate_with_heartbeat(model, prompt, section_name="intraday_analysis"):
            yield chunk

        yield f"data: {json.dumps({'type': 'section_end', 'section': 'intraday_analysis'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống'})}\n\n"

system_prompt_ta = """
You are a **professional, objective, and data-driven financial analyst and trading expert**. 
Use your extensive market knowledge and technical analysis expertise to generate a **clear, in-depth, and professional report** in Vietnamese.

**Task:**  
Select up to **8 key indicators** that best describe the given market or strategy. Avoid redundancy (e.g., RSI14 & Momentum RSI).  
Provide a **comprehensive analysis** covering:
- Trend direction & strength  
- Momentum & volatility  
- Volume confirmation  
- Possible reversal or continuation  
Explain all terms in full (e.g., “Average Directional Index” instead of “trend_adx”).  
Enrich the report with your own relevant knowledge when necessary.

**Indicators Reference (grouped):**
- *Price Data:* open, high, low, close, adjust, volume_match  
- *Moving Averages:* sma20, ema20, trend_sma_fast/slow, trend_ema_fast/slow  
- *MACD & Momentum:* macd, macd_signal, trend_macd, trend_macd_signal, rsi14, momentum_stoch, momentum_wr, momentum_ao, momentum_roc  
- *Bollinger & Volatility:* bb_high, bb_low, volatility_bbm, volatility_bbw, atr14  
- *Volume:* volume_adi, volume_obv, volume_cmf, volume_fi, volume_mfi, volume_vwap  
- *Advanced Trend:* Average Directional Index (ADX), +DI, -DI, CCI, Aroon Up/Down, Ichimoku Conversion/Base  

**Output Requirements:**  
- Write in **Vietnamese**, in a professional yet readable tone.  
- Be **objective, data-based, and insightful** — no speculation or emotional wording.  
- Structure the analysis logically, ending with a **Markdown summary table** listing:  
  *Indicator – Observation – Interpretation – Implication for traders*.
"""

system_prompt_news = """
You are a **professional financial analyst and news researcher**. 
Analyze recent news for a specific company. 
Use your **expert judgment and broad financial knowledge** to create a **clear, professional, and insightful report** in Vietnamese.

**Task:**  
- Summarize and interpret key news events that could affect the company's stock price, market perception, or trading activity.  
- Identify **positive, negative, and neutral** influences objectively.  
- Evaluate how each piece of news relates to:  
  *Market sentiment*, *company performance*, *investor confidence*, and *trading implications*.  
- Provide **data-driven insights**, not opinions or vague statements (avoid phrases like “mixed trend”).  
- Enrich your analysis with relevant financial context when needed.

**Output Requirements:**  
- Write in **Vietnamese**, in a professional and concise tone.  
- The report must be **well-structured, factual, and actionable** for traders.  
- End with a **Markdown table** summarizing key points:  
  *News Item – Impact – Interpretation – Implication for traders*.
"""

def get_news_for_ticker(ticker: str, asset_type: str = 'stock', look_back_days: int = 7) -> str:
    """
    Retrieve recent news about a given stock ticker.
    Args:
        ticker (str): The stock ticker symbol (e.g., "AAPL").
        curr_date (str): The current date in "yyyy-mm-dd" format.
        look_back_days (int): Number of days to look back for news.
    Returns:
        str: Formatted news string or empty string if no news found.
    """
    if asset_type == 'stock': news = fetch_google_news(f'Tin tức quan trọng mã chứng khoán {ticker}', datetime.now().strftime('%Y-%m-%d'), look_back_days)
    elif asset_type == 'crypto': news = fetch_google_news(f'Important news for crypto currencies ticket {ticker}', datetime.now().strftime('%Y-%m-%d'), look_back_days)
    return news

async def get_insights_streaming(ticker: str, asset_type: str = 'stock', start_date: str = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'), end_date: str = datetime.now().strftime('%Y-%m-%d'), look_back_days: int=30):
    """
    Streaming version of get_insights that yields chunks in real-time.
    Returns a generator that yields Server-Sent Events formatted data.
    """
    
    
    try:
        # Phase 1: Technical Analysis

        if asset_type == 'stock':
            df = load_stock_data_vnquant(ticker, asset_type, start_date, end_date)
        else:
            df = load_stock_data_yf(ticker, asset_type, start_date, end_date)
        df_ta = add_technical_indicators_yf(df)
        signals = detect_signals(df_ta)
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải dữ liệu chứng khoán...', 'progress': 10})}\n\n"
        
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích kỹ thuật...', 'progress': 15})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'technical_analysis', 'title': 'Phân Tích Kỹ Thuật'})}\n\n"
        
        try:
            prompt = f"""System: {system_prompt_ta}\n\n"
                        You are a professional analyst. Provide a deep, objective report for stock ticker {ticker}.
                        Focus only on technical and quantitative insights.
                        Given signals: '{signals}'."""
            # Create model instance
            model = genai.GenerativeModel('gemini-2.0-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="technical_analysis"):
                yield chunk
        except Exception:
            technical_content = f"Lỗi trong phân tích kỹ thuật"
            yield f"data: {json.dumps({'type': 'error', 'section': 'technical_analysis', 'message': technical_content})}\n\n"
            technical_content = None
        
        yield f"data: {json.dumps({'type': 'section_end', 'section': 'technical_analysis'})}\n\n"
        
        # Phase 2: News Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích tin tức...', 'progress': 30})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'news_analysis', 'title': 'Phân Tích Tin Tức'})}\n\n"
        news = get_news_for_ticker(ticker=ticker, asset_type=asset_type, look_back_days=30)
        try:
            prompt = f"""System: {system_prompt_news}\n\n
                        You are a professional financial analyst. Provide an objective and insightful news report for stock ticker {ticker}.
                        Focus only on the financial relevance and trading implications.
                        Given recent news data: '{news}'."""
            model = genai.GenerativeModel('gemini-2.0-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="news_analysis"):
                yield chunk
        except Exception:
            news_content = f"Lỗi trong phân tích tin tức"
            yield f"data: {json.dumps({'type': 'error', 'section': 'news_analysis', 'message': news_content})}\n\n"
            
        yield f"data: {json.dumps({'type': 'section_end', 'section': 'news_analysis'})}\n\n"

        # Phase 3: Proprietary Trading Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích giao dịch tự doanh...', 'progress': 45})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'proprietary_trading_analysis', 'title': 'Phân Tích Giao Dịch Tự Doanh'})}\n\n"

        # Bước 1: Lấy dữ liệu khớp lệnh
        data = get_proprietary_trading_data(symbol=ticker, start_date=None, end_date=None, page_index=1, page_size=14)["ListDataTudoanh"]
        df = pd.DataFrame(data)

        schema = {
            "Symbol": "Mã cổ phiếu",
            "Date": "Ngày giao dịch",
            "KLcpMua": "Khối lượng cổ phiếu tự doanh mua (cổ phiếu)",
            "KlcpBan": "Khối lượng cổ phiếu tự doanh bán (cổ phiếu)",
            "GtMua": "Giá trị tự doanh mua (đồng)",
            "GtBan": "Giá trị tự doanh bán (đồng)"
            }
        
        df_json = df.to_json(orient="records", force_ascii=False)
        df = json.dumps({
            "schema": schema,
            "records": json.loads(df_json)
        }, indent=2, ensure_ascii=False)

        yield f"data: {json.dumps({'type': 'status', 'message': 'Dữ liệu khớp lệnh đã sẵn sàng...'})}\n\n"

        # Bước 2: Tạo prompt cho phân tích
        prompt = f"""
        Bạn là chuyên gia phân tích tài chính chuyên nghiệp. 
        Hãy đánh giá chi tiết và chính xác mã cổ phiếu dựa trên dữ liệu giao dịch tự doanh dưới đây.
        Đưa ra các nhận định chuyên môn, giả thuyết hợp lý có cơ sở.
        Dữ liệu giao dịch tự doanh:
        {df}

        Yêu cầu:
        - Trả lời cực kì KHÁCH QUAN mang tính chuyên môn cao.
        - Đọc hiểu số liệu đã cung cấp thật chuyên sâu.
        - Phân tích hành vi giao dịch tự doanh.
        - Đánh giá xu hướng niềm tin và tác động tới giá cổ phiếu.
        - Đưa ra giả thuyết hợp lý, sáng tạo, có chiều sâu.
        - Không giải thích lại yêu cầu, không thêm lời mở đầu hoặc kết luận ngoài phân tích chính.
        """

        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích dữ liệu tự doanh...'})}\n\n"

        # Bước 3: Gọi mô hình Generative AI
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="proprietary_trading_analysis"):
                yield chunk
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'section': 'proprietary_trading_analysis', 'message': 'Lỗi trong quá trình phân tích'})}\n\n"

        yield f"data: {json.dumps({'type': 'section_end', 'section': 'proprietary_trading_analysis'})}\n\n"

        # Phase 4: Foreign Trading Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích giao dịch khối ngoại...', 'progress': 60})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'foreign_trading_analysis', 'title': 'Phân Tích Giao Dịch Khối Ngoại'})}\n\n"
        # Bước 1: Lấy dữ liệu khớp lệnh
        data = get_foreign_trading_data(symbol=ticker, start_date=None, end_date=None, page_index=1, page_size=14)
        df = pd.DataFrame(data)

        schema = {
            "Ngay": "Ngày giao dịch",
            "KLGDRong": "Khối lượng giao dịch ròng (mua trừ bán)",
            "GTDGRong": "Giá trị giao dịch ròng (tỷ đồng, mua trừ bán)",
            "ThayDoi": "Biến động giá cổ phiếu trong ngày (%)",
            "KLMua": "Tổng khối lượng mua của khối ngoại",
            "GtMua": "Tổng giá trị mua của khối ngoại (tỷ đồng)",
            "KLBan": "Tổng khối lượng bán của khối ngoại",
            "GtBan": "Tổng giá trị bán của khối ngoại (tỷ đồng)",
            "RoomConLai": "Tỷ lệ room ngoại còn lại có thể mua (%)",
            "DangSoHuu": "Tỷ lệ sở hữu hiện tại của khối ngoại (%)"
            }
        
        df_json = df.to_json(orient="records", force_ascii=False)
        df = json.dumps({
            "schema": schema,
            "records": json.loads(df_json)
        }, indent=2, ensure_ascii=False)

        yield f"data: {json.dumps({'type': 'status', 'message': 'Dữ liệu khớp lệnh đã sẵn sàng...'})}\n\n"

        # Bước 2: Tạo prompt cho phân tích
        prompt = f"""
        Bạn là chuyên gia phân tích tài chính chuyên nghiệp. 
        Hãy đánh giá chi tiết và chính xác mã cổ phiếu dựa trên dữ liệu giao dịch khối ngoại quốc dưới đây.
        Đưa ra các nhận định chuyên môn, giả thuyết hợp lý có cơ sở.
        Dữ liệu giao dịch khối ngoại quốc:
        {df}

        Yêu cầu:
        - Trả lời cực kì KHÁCH QUAN mang tính chuyên môn cao.
        - Đọc hiểu số liệu đã cung cấp thật chuyên sâu.
        - Phân tích hành vi giao dịch của khối ngoại.
        - Đánh giá xu hướng niềm tin và tác động tới giá cổ phiếu.
        - Đưa ra giả thuyết hợp lý, sáng tạo, có chiều sâu.
        - Không giải thích lại yêu cầu, không thêm lời mở đầu hoặc kết luận ngoài phân tích chính.
        """

        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích dữ liệu khối ngoại...'})}\n\n"

        # Bước 3: Gọi mô hình Generative AI
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="foreign_trading_analysis"):
                yield chunk
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'section': 'foreign_trading_analysis', 'message': 'Lỗi trong quá trình phân tích'})}\n\n"

        yield f"data: {json.dumps({'type': 'section_end', 'section': 'foreign_trading_analysis'})}\n\n"

        # Phase 5: Shareholder Trading Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích giao dịch cổ đông...', 'progress': 75})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'shareholder_trading_analysis', 'title': 'Phân Tích Giao Dịch Cổ Đông Nội Bộ'})}\n\n"
        # Bước 1: Lấy dữ liệu khớp lệnh
        data = get_shareholder_data(symbol=ticker, start_date=None, end_date=None, page_index=1, page_size=14)
        df = pd.DataFrame(data)
        df.drop(columns=['ShareHolderCode', 'HolderID'], inplace=True)

        schema = {
            "Stock": "Mã cổ phiếu",
            "TransactionMan": "Người thực hiện giao dịch (cổ đông hoặc tổ chức)",
            "TransactionManPosition": "Chức vụ của người giao dịch trong công ty",
            "RelatedMan": "Người hoặc tổ chức có liên quan đến người giao dịch",
            "RelatedManPosition": "Chức vụ của người liên quan (nếu có)",
            "VolumeBeforeTransaction": "Số lượng cổ phiếu nắm giữ trước giao dịch",
            "PlanBuyVolume": "Số lượng cổ phiếu dự kiến mua",
            "PlanSellVolume": "Số lượng cổ phiếu dự kiến bán",
            "PlanBeginDate": "Ngày bắt đầu kế hoạch giao dịch",
            "PlanEndDate": "Ngày kết thúc kế hoạch giao dịch",
            "RealBuyVolume": "Số lượng cổ phiếu thực tế đã mua",
            "RealSellVolume": "Số lượng cổ phiếu thực tế đã bán",
            "RealEndDate": "Ngày hoàn tất giao dịch thực tế",
            "PublishedDate": "Ngày công bố thông tin giao dịch",
            "VolumeAfterTransaction": "Số lượng cổ phiếu còn lại sau giao dịch",
            "TransactionNote": "Ghi chú hoặc mục đích giao dịch (nếu có)",
            "TyLeSoHuu": "Tỷ lệ sở hữu cổ phần sau giao dịch (%)",
            "OrderDate": "Ngày đặt lệnh giao dịch"
            }
        
        df_json = df.to_json(orient="records", force_ascii=False)
        df = json.dumps({
            "schema": schema,
            "records": json.loads(df_json)
        }, indent=2, ensure_ascii=False)

        yield f"data: {json.dumps({'type': 'status', 'message': 'Dữ liệu khớp lệnh đã sẵn sàng...'})}\n\n"

        # Bước 2: Tạo prompt cho phân tích
        prompt = f"""
        Bạn là chuyên gia phân tích tài chính chuyên nghiệp. 
        Hãy đánh giá chi tiết và chính xác mã cổ phiếu dựa trên dữ liệu giao dịch cổ đông nội bộ dưới đây.
        Đưa ra các nhận định chuyên môn, giả thuyết hợp lý có cơ sở.
        Dữ liệu giao dịch giữa cổ đông của công ty:
        {df}

        Yêu cầu:
        - Trả lời cực kì KHÁCH QUAN mang tính chuyên môn cao.
        - Đọc hiểu số liệu đã cung cấp thật chuyên sâu.
        - Phân tích hành vi giao dịch của cổ đông nội bộ.
        - Đánh giá xu hướng niềm tin và tác động tới giá cổ phiếu.
        - Đưa ra giả thuyết hợp lý, sáng tạo, có chiều sâu.
        - Không giải thích lại yêu cầu, không thêm lời mở đầu hoặc kết luận ngoài phân tích chính.
        """

        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích dữ liệu giao dịch cổ đông...'})}\n\n"

        # Bước 3: Gọi mô hình Generative AI
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="shareholder_trading_analysis"):
                yield chunk
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'section': 'shareholder_trading_analysis', 'message': 'Lỗi trong quá trình phân tích'})}\n\n"

        yield f"data: {json.dumps({'type': 'section_end', 'section': 'shareholder_trading_analysis'})}\n\n"
    
        # Completion
        yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích hoàn tất!', 'progress': 100})}\n\n"
        
    except Exception:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống'})}\n\n"

# ==================== SEPARATE PHASE FUNCTIONS ====================

async def get_technical_analysis_streaming(ticker: str, asset_type: str = 'stock', start_date: str = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'), end_date: str = datetime.now().strftime('%Y-%m-%d')):
    """
    Technical analysis phase separated from get_insights_streaming.
    Returns a generator that yields Server-Sent Events formatted data.
    """
    
    try:
        # Phase 1: Technical Analysis
        if asset_type == 'stock':
            df = load_stock_data_vnquant(ticker, asset_type, start_date, end_date)
        else:
            df = load_stock_data_yf(ticker, asset_type, start_date, end_date)
        df_ta = add_technical_indicators_yf(df)
        signals = detect_signals(df_ta)
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải dữ liệu chứng khoán...', 'progress': 10})}\n\n"
        
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích kỹ thuật...', 'progress': 50})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'technical_analysis', 'title': 'Phân Tích Kỹ Thuật'})}\n\n"
        
        try:
            prompt = f"""System: {system_prompt_ta}\n\n"
                        You are a professional analyst. Provide a deep, objective report for stock ticker {ticker}.
                        Focus only on technical and quantitative insights.
                        Given signals: '{signals}'."""
            # Create model instance
            model = genai.GenerativeModel('gemini-2.0-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="technical_analysis"):
                yield chunk
        except Exception:
            technical_content = f"Lỗi trong phân tích kỹ thuật"
            yield f"data: {json.dumps({'type': 'error', 'section': 'technical_analysis', 'message': technical_content})}\n\n"
        
        yield f"data: {json.dumps({'type': 'section_end', 'section': 'technical_analysis'})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích kỹ thuật hoàn tất!', 'progress': 100})}\n\n"
        
    except Exception:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống trong phân tích kỹ thuật'})}\n\n"

async def get_news_analysis_streaming(ticker: str, asset_type: str = 'stock', look_back_days: int = 30):
    """
    News analysis phase separated from get_insights_streaming.
    Returns a generator that yields Server-Sent Events formatted data.
    """
    try:
        # Phase 2: News Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích tin tức...', 'progress': 50})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'news_analysis', 'title': 'Phân Tích Tin Tức'})}\n\n"
        news = get_news_for_ticker(ticker=ticker, asset_type=asset_type, look_back_days=look_back_days)
        try:
            prompt = f"""System: {system_prompt_news}\n\n
                        You are a professional financial analyst. Provide an objective and insightful news report for stock ticker {ticker}.
                        Focus only on the financial relevance and trading implications.
                        Given recent news data: '{news}'."""
            model = genai.GenerativeModel('gemini-2.0-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="news_analysis"):
                yield chunk
        except Exception:
            news_content = f"Lỗi trong phân tích tin tức"
            yield f"data: {json.dumps({'type': 'error', 'section': 'news_analysis', 'message': news_content})}\n\n"
            
        yield f"data: {json.dumps({'type': 'section_end', 'section': 'news_analysis'})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích tin tức hoàn tất!', 'progress': 100})}\n\n"
        
    except Exception:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống trong phân tích tin tức'})}\n\n"

async def get_proprietary_trading_analysis_streaming(ticker: str):
    """
    Proprietary trading analysis phase separated from get_insights_streaming.
    Returns a generator that yields Server-Sent Events formatted data.
    """
    try:
        # Phase 3: Proprietary Trading Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích giao dịch tự doanh...', 'progress': 10})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'proprietary_trading_analysis', 'title': 'Phân Tích Giao Dịch Tự Doanh'})}\n\n"

        # Bước 1: Lấy dữ liệu khớp lệnh
        data = get_proprietary_trading_data(symbol=ticker, start_date=None, end_date=None, page_index=1, page_size=14)["ListDataTudoanh"]
        df = pd.DataFrame(data)

        schema = {
            "Symbol": "Mã cổ phiếu",
            "Date": "Ngày giao dịch",
            "KLcpMua": "Khối lượng cổ phiếu tự doanh mua (cổ phiếu)",
            "KlcpBan": "Khối lượng cổ phiếu tự doanh bán (cổ phiếu)",
            "GtMua": "Giá trị tự doanh mua (đồng)",
            "GtBan": "Giá trị tự doanh bán (đồng)"
            }
        
        df_json = df.to_json(orient="records", force_ascii=False)
        df = json.dumps({
            "schema": schema,
            "records": json.loads(df_json)
        }, indent=2, ensure_ascii=False)

        yield f"data: {json.dumps({'type': 'status', 'message': 'Dữ liệu khớp lệnh đã sẵn sàng...','progress': 50})}\n\n"

        # Bước 2: Tạo prompt cho phân tích
        prompt = f"""
        Bạn là chuyên gia phân tích tài chính chuyên nghiệp. 
        Hãy đánh giá chi tiết và chính xác mã cổ phiếu dựa trên dữ liệu giao dịch tự doanh dưới đây.
        Đưa ra các nhận định chuyên môn, giả thuyết hợp lý có cơ sở.
        Dữ liệu giao dịch tự doanh:
        {df}

        Yêu cầu:
        - Trả lời cực kì KHÁCH QUAN mang tính chuyên môn cao.
        - Đọc hiểu số liệu đã cung cấp thật chuyên sâu.
        - Phân tích hành vi giao dịch tự doanh.
        - Đánh giá xu hướng niềm tin và tác động tới giá cổ phiếu.
        - Đưa ra giả thuyết hợp lý, sáng tạo, có chiều sâu.
        - Không giải thích lại yêu cầu, không thêm lời mở đầu hoặc kết luận ngoài phân tích chính.
        """

        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích dữ liệu tự doanh...'})}\n\n"

        # Bước 3: Gọi mô hình Generative AI
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="proprietary_trading_analysis"):
                yield chunk
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'section': 'proprietary_trading_analysis', 'message': 'Lỗi trong quá trình phân tích'})}\n\n"

        yield f"data: {json.dumps({'type': 'section_end', 'section': 'proprietary_trading_analysis'})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích giao dịch tự doanh hoàn tất!', 'progress': 100})}\n\n"
        
    except Exception:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống trong phân tích giao dịch tự doanh'})}\n\n"

async def get_foreign_trading_analysis_streaming(ticker: str):
    """
    Foreign trading analysis phase separated from get_insights_streaming.
    Returns a generator that yields Server-Sent Events formatted data.
    """
    
    
    try:
        # Phase 4: Foreign Trading Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích giao dịch khối ngoại...', 'progress': 10})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'foreign_trading_analysis', 'title': 'Phân Tích Giao Dịch Khối Ngoại'})}\n\n"
        # Bước 1: Lấy dữ liệu khớp lệnh
        data = get_foreign_trading_data(symbol=ticker, start_date=None, end_date=None, page_index=1, page_size=14)
        df = pd.DataFrame(data)

        schema = {
            "Ngay": "Ngày giao dịch",
            "KLGDRong": "Khối lượng giao dịch ròng (mua trừ bán)",
            "GTDGRong": "Giá trị giao dịch ròng (tỷ đồng, mua trừ bán)",
            "ThayDoi": "Biến động giá cổ phiếu trong ngày (%)",
            "KLMua": "Tổng khối lượng mua của khối ngoại",
            "GtMua": "Tổng giá trị mua của khối ngoại (tỷ đồng)",
            "KLBan": "Tổng khối lượng bán của khối ngoại",
            "GtBan": "Tổng giá trị bán của khối ngoại (tỷ đồng)",
            "RoomConLai": "Tỷ lệ room ngoại còn lại có thể mua (%)",
            "DangSoHuu": "Tỷ lệ sở hữu hiện tại của khối ngoại (%)"
            }
        
        df_json = df.to_json(orient="records", force_ascii=False)
        df = json.dumps({
            "schema": schema,
            "records": json.loads(df_json)
        }, indent=2, ensure_ascii=False)

        yield f"data: {json.dumps({'type': 'status', 'message': 'Dữ liệu khớp lệnh đã sẵn sàng...', 'progress': 50})}\n\n"

        # Bước 2: Tạo prompt cho phân tích
        prompt = f"""
        Bạn là chuyên gia phân tích tài chính chuyên nghiệp. 
        Hãy đánh giá chi tiết và chính xác mã cổ phiếu dựa trên dữ liệu giao dịch khối ngoại quốc dưới đây.
        Đưa ra các nhận định chuyên môn, giả thuyết hợp lý có cơ sở.
        Dữ liệu giao dịch khối ngoại quốc:
        {df}

        Yêu cầu:
        - Trả lời cực kì KHÁCH QUAN mang tính chuyên môn cao.
        - Đọc hiểu số liệu đã cung cấp thật chuyên sâu.
        - Phân tích hành vi giao dịch của khối ngoại.
        - Đánh giá xu hướng niềm tin và tác động tới giá cổ phiếu.
        - Đưa ra giả thuyết hợp lý, sáng tạo, có chiều sâu.
        - Không giải thích lại yêu cầu, không thêm lời mở đầu hoặc kết luận ngoài phân tích chính.
        """

        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích dữ liệu khối ngoại...'})}\n\n"

        # Bước 3: Gọi mô hình Generative AI
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="foreign_trading_analysis"):
                yield chunk
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'section': 'foreign_trading_analysis', 'message': 'Lỗi trong quá trình phân tích'})}\n\n"

        yield f"data: {json.dumps({'type': 'section_end', 'section': 'foreign_trading_analysis'})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích giao dịch khối ngoại hoàn tất!', 'progress': 100})}\n\n"
        
    except Exception:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống trong phân tích giao dịch khối ngoại'})}\n\n"

async def get_shareholder_trading_analysis_streaming(ticker: str):
    """
    Shareholder trading analysis phase separated from get_insights_streaming.
    Returns a generator that yields Server-Sent Events formatted data.
    """
    try:
        # Phase 5: Shareholder Trading Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích giao dịch cổ đông...', 'progress': 10})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'shareholder_trading_analysis', 'title': 'Phân Tích Giao Dịch Cổ Đông Nội Bộ'})}\n\n"
        # Bước 1: Lấy dữ liệu khớp lệnh
        data = get_shareholder_data(symbol=ticker, start_date=None, end_date=None, page_index=1, page_size=14)
        df = pd.DataFrame(data)
        df.drop(columns=['ShareHolderCode', 'HolderID'], inplace=True)

        schema = {
            "Stock": "Mã cổ phiếu",
            "TransactionMan": "Người thực hiện giao dịch (cổ đông hoặc tổ chức)",
            "TransactionManPosition": "Chức vụ của người giao dịch trong công ty",
            "RelatedMan": "Người hoặc tổ chức có liên quan đến người giao dịch",
            "RelatedManPosition": "Chức vụ của người liên quan (nếu có)",
            "VolumeBeforeTransaction": "Số lượng cổ phiếu nắm giữ trước giao dịch",
            "PlanBuyVolume": "Số lượng cổ phiếu dự kiến mua",
            "PlanSellVolume": "Số lượng cổ phiếu dự kiến bán",
            "PlanBeginDate": "Ngày bắt đầu kế hoạch giao dịch",
            "PlanEndDate": "Ngày kết thúc kế hoạch giao dịch",
            "RealBuyVolume": "Số lượng cổ phiếu thực tế đã mua",
            "RealSellVolume": "Số lượng cổ phiếu thực tế đã bán",
            "RealEndDate": "Ngày hoàn tất giao dịch thực tế",
            "PublishedDate": "Ngày công bố thông tin giao dịch",
            "VolumeAfterTransaction": "Số lượng cổ phiếu còn lại sau giao dịch",
            "TransactionNote": "Ghi chú hoặc mục đích giao dịch (nếu có)",
            "TyLeSoHuu": "Tỷ lệ sở hữu cổ phần sau giao dịch (%)",
            "OrderDate": "Ngày đặt lệnh giao dịch"
            }
        
        df_json = df.to_json(orient="records", force_ascii=False)
        df = json.dumps({
            "schema": schema,
            "records": json.loads(df_json)
        }, indent=2, ensure_ascii=False)

        yield f"data: {json.dumps({'type': 'status', 'message': 'Dữ liệu khớp lệnh đã sẵn sàng...', 'progress': 50})}\n\n"

        # Bước 2: Tạo prompt cho phân tích
        prompt = f"""
        Bạn là chuyên gia phân tích tài chính chuyên nghiệp. 
        Hãy đánh giá chi tiết và chính xác mã cổ phiếu dựa trên dữ liệu giao dịch cổ đông nội bộ dưới đây.
        Đưa ra các nhận định chuyên môn, giả thuyết hợp lý có cơ sở.
        Dữ liệu giao dịch giữa cổ đông của công ty:
        {df}

        Yêu cầu:
        - Trả lời cực kì KHÁCH QUAN mang tính chuyên môn cao.
        - Đọc hiểu số liệu đã cung cấp thật chuyên sâu.
        - Phân tích hành vi giao dịch của cổ đông nội bộ.
        - Đánh giá xu hướng niềm tin và tác động tới giá cổ phiếu.
        - Đưa ra giả thuyết hợp lý, sáng tạo, có chiều sâu.
        - Không giải thích lại yêu cầu, không thêm lời mở đầu hoặc kết luận ngoài phân tích chính.
        """

        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích dữ liệu giao dịch cổ đông...'})}\n\n"

        # Bước 3: Gọi mô hình Generative AI
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            async for chunk in generate_with_heartbeat(model, prompt, section_name="shareholder_trading_analysis"):
                yield chunk
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'section': 'shareholder_trading_analysis', 'message': 'Lỗi trong quá trình phân tích'})}\n\n"

        yield f"data: {json.dumps({'type': 'section_end', 'section': 'shareholder_trading_analysis'})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích giao dịch cổ đông hoàn tất!', 'progress': 100})}\n\n"
        
    except Exception:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống trong phân tích giao dịch cổ đông'})}\n\n"

async def fetch_news_streaming(
    symbol: str,
    asset_type: str = 'stock',
    look_back_days: int = 30,
    pages: int = 2,
    max_results: int = 50,
    news_sources: List[str] = ['google']
):
    """
    Streaming version of news fetching that yields chunks in real-time.
    Returns a generator that yields Server-Sent Events formatted data.
    """
    import json
    import asyncio
    import time
    from datetime import datetime, timedelta
    
    symbol = symbol.upper().strip()
    
    async def send_heartbeat_during_operation(operation_name: str, progress: int = 0):
        """Send heartbeat during long operations"""
        yield f"data: {json.dumps({'type': 'status', 'message': f'🤖 Đang {operation_name}...', 'progress': progress, 'heartbeat': True})}\n\n"
        await asyncio.sleep(0.1)
    
    try:
        # Initialize news aggregation
        aggregated_news = []
        news_stats = {
            'total_articles': 0,
            'sources_used': [],
            'date_range': {
                'from': (datetime.now() - timedelta(days=look_back_days)).strftime('%Y-%m-%d'),
                'to': datetime.now().strftime('%Y-%m-%d')
            },
            'processing_time': 0
        }
        
        start_time = datetime.now()
        
        # Yield initial status
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang khởi tạo tìm kiếm tin tức...', 'progress': 5})}\n\n"
        
        # Yield news collection start
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'news_collection', 'title': f'Thu Thập Tin Tức - {symbol}'})}\n\n"
        
        # (universal source)
        if 'google' in news_sources:
            try:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tìm kiếm trên Google News...', 'progress': 20})}\n\n"
                message = f'🔍 **Đang tìm kiếm tin tức về {symbol} trên Google News...**\n\n'
                yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"

                # Create search query based on stock type
                if asset_type == 'stock':
                    # Remove .VN suffix for Vietnamese stocks
                    clean_symbol = symbol.replace('.VN', '')
                    search_query = f"tin tức cổ phiếu {clean_symbol} OR công ty {clean_symbol} OR mã {clean_symbol}"
                elif asset_type == 'crypto':
                    search_query = f"Important news for crypto currencies ticket {symbol}"

                # Add heartbeat before long operation
                async for heartbeat in send_heartbeat_during_operation("Tìm kiếm tin tức", 25):
                    yield heartbeat

                google_news = fetch_google_news(
                    search_query,
                    datetime.now().strftime('%Y-%m-%d'),
                    look_back_days
                )
                
                if google_news:
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Đang xử lý kết quả...', 'progress': 40})}\n\n"
                    
                    # Parse format with heartbeat
                    async for heartbeat in send_heartbeat_during_operation("Phân tích cú pháp tin tức", 42):
                        yield heartbeat
                    
                    from app_fastapi import parse_google_news_format
                    google_articles = parse_google_news_format(google_news, 'Google News')
                    
                    message = f'✅ **Tìm thấy {len(google_articles)} bài viết từ Google News**\n\n'
                    yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"

                    # Stream individual articles with heartbeat
                    total_articles = len(google_articles[:max_results//2])
                    for i, article in enumerate(google_articles[:max_results//2]):
                        aggregated_news.append(article)
                        
                        # Stream article info
                        article_text = f"📰 **{article.get('title', 'No title')}**\\n"
                        article_text += f"📅 {article.get('date', 'No date')} | 🔗 {article.get('source', 'Unknown source')}\\n"
                        article_text += f"📊 Điểm liên quan: {article.get('relevance_score', 0):.1f}\\n\\n"
                        
                        yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': article_text})}\n\n"
                        
                        # Update progress
                        progress = min(40 + (i / total_articles) * 30, 70)
                        yield f"data: {json.dumps({'type': 'status', 'message': f'Đã xử lý {i+1}/{total_articles} bài viết...', 'progress': progress})}\n\n"
                        
                        # Small delay for streaming effect with async support
                        await asyncio.sleep(0.1)
                    
                    news_stats['sources_used'].append('google')
                    
                else:
                    message = '⚠️ **Không tìm thấy tin tức từ Google News**\\n\\n'
                    yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"
                    
            except Exception as e:
                error_msg = f"❌ **Lỗi khi tìm kiếm:** {str(e)}\\n\\n"
                yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': error_msg})}\n\n"
        
        # Process and enhance news with heartbeat
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang xử lý và phân tích tin tức...', 'progress': 75})}\n\n"
        
        # Remove duplicates based on title similarity with heartbeat
        if aggregated_news:
            message = '🔄 **Đang loại bỏ tin tức trùng lặp...**\\n\\n'
            yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"
            
            # Add heartbeat for duplicate removal
            async for heartbeat in send_heartbeat_during_operation("Loại bỏ tin tức trùng lặp", 77):
                yield heartbeat
            
            from app_fastapi import remove_duplicate_news
            original_count = len(aggregated_news)
            aggregated_news = remove_duplicate_news(aggregated_news)
            removed_count = original_count - len(aggregated_news)
            
            if removed_count > 0:
                message = f'✅ **Đã loại bỏ {removed_count} tin tức trùng lặp**\\n\\n'
                yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"
        
        # Add sentiment analysis with heartbeat
        if aggregated_news:
            message = '🧠 **Đang phân tích cảm xúc tin tức...**\\n\\n'
            yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"
            
            # Add heartbeat for sentiment analysis
            async for heartbeat in send_heartbeat_during_operation("Phân tích cảm xúc tin tức", 80):
                yield heartbeat
            
            from app_fastapi import enhance_news_with_sentiment
            aggregated_news = enhance_news_with_sentiment(aggregated_news)
            
            # Show sentiment summary
            positive_count = sum(1 for news in aggregated_news if news.get('sentiment') == 'positive')
            negative_count = sum(1 for news in aggregated_news if news.get('sentiment') == 'negative')
            neutral_count = len(aggregated_news) - positive_count - negative_count
            
            sentiment_text = f"📊 **Phân tích cảm xúc:**\\n"
            sentiment_text += f"📈 Tích cực: {positive_count} bài\\n"
            sentiment_text += f"📉 Tiêu cực: {negative_count} bài\\n"
            sentiment_text += f"📊 Trung tính: {neutral_count} bài\\n\\n"
            
            yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': sentiment_text})}\n\n"
        
        # Sort by relevance score and date with heartbeat
        if aggregated_news:
            async for heartbeat in send_heartbeat_during_operation("Sắp xếp tin tức theo độ liên quan", 85):
                yield heartbeat
            aggregated_news.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Limit results
        aggregated_news = aggregated_news[:max_results]
        
        # Update statistics
        news_stats['total_articles'] = len(aggregated_news)
        news_stats['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        # End news collection section
        yield f"data: {json.dumps({'type': 'section_end', 'section': 'news_collection'})}\n\n"
        
        # Start news results section
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang chuẩn bị kết quả...', 'progress': 90})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'news_results', 'title': f'Kết Quả Tin Tức - {len(aggregated_news)} bài viết'})}\n\n"
        
        # Stream final results with heartbeat for large datasets
        if aggregated_news:
            total_news = len(aggregated_news)
            for i, news in enumerate(aggregated_news):
                news_data = {
                    'id': news.get('id', ''),
                    'title': news.get('title', 'No title'),
                    'content': news.get('content', news.get('snippet', news.get('summary', news.get('description', 'No content available')))),
                    'sentiment': news.get('sentiment', 'neutral'),
                    'score': news.get('sentiment_score', news.get('relevance_score', 0)),
                    'publishedAt': news.get('published_at', news.get('date', datetime.now().isoformat())),
                    'source': news.get('source', 'Unknown'),
                    'url': news.get('url', news.get('link', '#'))  # Add URL field
                }
                
                yield f"data: {json.dumps({'type': 'news_item', 'section': 'news_results', 'data': news_data})}\n\n"
                
                # Add heartbeat every 10 items for large datasets
                if total_news > 20 and (i + 1) % 10 == 0:
                    progress = 90 + ((i + 1) / total_news) * 8
                    async for heartbeat in send_heartbeat_during_operation(f"Đang truyền tin tức ({i+1}/{total_news})", int(progress)):
                        yield heartbeat
                
                # Small delay for streaming effect
                await asyncio.sleep(0.05)
        else:
            message = '⚠️ **Không tìm thấy tin tức nào phù hợp.**\\n\\n'
            yield f"data: {json.dumps({'type': 'content', 'section': 'news_results', 'text': message})}\n\n"
        
        # End news results section
        yield f"data: {json.dumps({'type': 'section_end', 'section': 'news_results'})}\n\n"
        
        # Final response data with heartbeat
        async for heartbeat in send_heartbeat_during_operation("Chuẩn bị dữ liệu cuối cùng", 98):
            yield heartbeat
            
        final_response = {
            'status': 'success',
            'data': aggregated_news,
            'symbol': symbol,
            'metadata': {
                'symbol_type': 'vietnamese' if not any(char in symbol for char in ['.', ':']) or symbol.endswith('.VN') else 'global',
                'search_parameters': {
                    'symbol': symbol,
                    'pages': pages,
                    'look_back_days': look_back_days,
                    'news_sources': news_sources,
                    'max_results': max_results
                },
                'statistics': news_stats
            }
        }
        
        # Send final data
        yield f"data: {json.dumps({'type': 'final_data', 'data': final_response})}\n\n"
        
        # Completion
        yield f"data: {json.dumps({'type': 'complete', 'message': f'Hoàn tất! Tìm thấy {len(aggregated_news)} tin tức về {symbol}', 'progress': 100})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống: {str(e)}'})}\n\n"

# if __name__ == "__main__":
#     print(get_shareholder_transaction_analysis_streaming("VIC"))