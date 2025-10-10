import google.generativeai as genai

from data_loader import load_stock_data_vnquant, load_stock_data_yf, load_stock_data_vn
from feature_engineering import *
from technical_analysis import *

import json
import requests
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

# Configure the API key
genai.configure(api_key='AIzaSyDYZrQbhP6fc0LHdM1XkESfoCcnUv92jFY')

system_prompt_ta = (
    """You are a trading assistant tasked with analyzing financial markets. Your role is to select the **most relevant indicators** for a given market condition or trading strategy from the following list. The goal is to choose up to **8 indicators** that provide complementary insights without redundancy. Categories and each category's indicators are:

Price & Basic Data:
- date: Timestamp for data points
- code: Stock/asset identifier
- high: Daily high price
- low: Daily low price
- open: Opening price
- close: Closing price
- adjust: Adjusted closing price
- volume_match: Trading volume

Moving Averages & Trend:
- sma20: 20-period Simple Moving Average: A short to medium-term trend indicator. Usage: Identify trend direction and dynamic support/resistance. Tips: Combines with price action for trend confirmation.
- ema20: 20-period Exponential Moving Average: More responsive than SMA. Usage: Capture quicker trend changes and momentum shifts. Tips: Less lag but more sensitive to noise.
- trend_sma_fast: Fast SMA for trend analysis. Usage: Short-term trend identification. Tips: Use with slow SMA for crossover signals.
- trend_sma_slow: Slow SMA for trend analysis. Usage: Long-term trend confirmation. Tips: Provides stable trend direction.
- trend_ema_fast: Fast EMA for trend analysis. Usage: Responsive trend tracking. Tips: Better for volatile markets.
- trend_ema_slow: Slow EMA for trend analysis. Usage: Trend confirmation with less noise. Tips: Balances responsiveness and stability.

MACD Related:
- macd: MACD line: Momentum indicator showing relationship between two EMAs. Usage: Identify trend changes and momentum shifts. Tips: Look for divergences and crossovers.
- macd_signal: MACD Signal line: Smoothed version of MACD. Usage: Generate buy/sell signals via crossovers. Tips: Confirm with other indicators.
- trend_macd: Trend-focused MACD calculation. Usage: Trend momentum analysis. Tips: Combine with price action.
- trend_macd_signal: Trend MACD signal line. Usage: Trend-based signal generation. Tips: Less noisy than standard MACD.
- trend_macd_diff: MACD histogram equivalent. Usage: Visualize momentum strength. Tips: Early divergence detection.

Momentum Indicators:
- rsi14: 14-period RSI: Measures momentum and overbought/oversold conditions. Usage: 70/30 thresholds for reversal signals. Tips: Watch for divergences in trending markets.
- momentum_rsi: Alternative RSI calculation. Usage: Momentum analysis with different parameters. Tips: Compare with standard RSI for confirmation.
- momentum_stoch: Stochastic oscillator. Usage: Overbought/oversold conditions. Tips: Use %K and %D crossovers.
- momentum_stoch_signal: Stochastic signal line. Usage: Smooth stochastic signals. Tips: Reduces false signals.
- momentum_wr: Williams %R: Momentum oscillator. Usage: Overbought/oversold identification. Tips: Inverse scale to RSI.
- momentum_ao: Awesome Oscillator: Momentum indicator. Usage: Momentum changes and divergences. Tips: Color changes indicate momentum shifts.
- momentum_roc: Rate of Change: Price momentum measure. Usage: Velocity of price changes. Tips: Leading indicator for trend changes.

Bollinger Bands & Volatility:
- bb_high: Bollinger Band upper limit. Usage: Overbought conditions and breakout levels. Tips: Price may ride bands in strong trends.
- bb_low: Bollinger Band lower limit. Usage: Oversold conditions and support levels. Tips: Confirm reversals with other indicators.
- volatility_bbm: Bollinger Band middle (basis). Usage: Dynamic support/resistance. Tips: Trend direction indicator.
- volatility_bbh: Bollinger Band high. Usage: Volatility-based resistance. Tips: Breakouts signal trend continuation.
- volatility_bbl: Bollinger Band low. Usage: Volatility-based support. Tips: Bounces indicate potential reversals.
- volatility_bbw: Bollinger Band width. Usage: Volatility measurement. Tips: Narrow bands precede volatility expansion.
- volatility_bbp: Bollinger Band position. Usage: Relative position within bands. Tips: Extreme values signal potential reversals.
- atr14: 14-period Average True Range: Volatility measure. Usage: Stop-loss placement and position sizing. Tips: Higher ATR requires wider stops.
- volatility_atr: Alternative ATR calculation. Usage: Volatility analysis. Tips: Risk management tool.

Volume Indicators:
- volume_adi: Accumulation/Distribution Index: Volume-price relationship. Usage: Confirm trends with volume analysis. Tips: Divergences signal potential reversals.
- volume_obv: On-Balance Volume: Cumulative volume indicator. Usage: Trend confirmation through volume. Tips: Leading indicator for price movements.
- volume_cmf: Chaikin Money Flow: Volume-weighted price indicator. Usage: Money flow analysis. Tips: Positive values indicate buying pressure.
- volume_fi: Force Index: Price and volume momentum. Usage: Trend strength measurement. Tips: Combines price change with volume.
- volume_mfi: Money Flow Index: Volume-based RSI. Usage: Overbought/oversold with volume. Tips: More reliable than price-only oscillators.
- volume_vwap: Volume Weighted Average Price: Intraday benchmark. Usage: Fair value reference. Tips: Institutional trading benchmark.

Advanced Trend Indicators:
- trend_adx: Average Directional Index: Trend strength measure. Usage: Determine if market is trending. Tips: Values above 25 indicate strong trends.
- trend_adx_pos: +DI component of ADX. Usage: Bullish trend strength. Tips: Compare with -DI for trend direction.
- trend_adx_neg: -DI component of ADX. Usage: Bearish trend strength. Tips: Crossovers with +DI signal trend changes.
- trend_cci: Commodity Channel Index: Cyclical indicator. Usage: Overbought/oversold and trend changes. Tips: Extreme values indicate potential reversals.
- trend_aroon_up: Aroon Up indicator. Usage: Bullish trend identification. Tips: Values above 70 indicate strong uptrend.
- trend_aroon_down: Aroon Down indicator. Usage: Bearish trend identification. Tips: Values above 70 indicate strong downtrend.
- trend_ichimoku_conv: Ichimoku Conversion Line: Short-term trend. Usage: Quick trend changes. Tips: Use with other Ichimoku components.
- trend_ichimoku_base: Ichimoku Base Line: Medium-term trend. Usage: Trend confirmation. Tips: Support/resistance levels.

These are only some examples, you must extend your knowledge to all indicators of techinal analysis to provide a highly professional, efficient, detailed and fine-grained analysis and insights that may help traders make decisions.

Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi14 and momentum_rsi unless specifically needed for comparison). Also briefly explain why they are suitable for the given market context. Write a very detailed and nuanced report of the trends you observe. Do not simply state the trends are mixed, provide detailed and fine-grained analysis and insights that may help traders make decisions."""
    + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
)

system_prompt_news = (
            "You are a news researcher tasked with analyzing recent news and trends over the past week of a specific company. Please write a comprehensive report of the current state that is relevant for trading. Do not simply state the trends are mixed, provide detailed and finegrained analysis and insights that may help traders make decisions."
            + """ Make sure to append a Makrdown table at the end of the report to organize key points in the report, organized and easy to read."""
        )

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

def get_insights(ticker: str, asset_type: str = 'stock', start_date: str = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'), end_date: str = datetime.now().strftime('%Y-%m-%d'), look_back_days: int=30):
    ticker = ticker.upper()
    if asset_type == 'stock':
        df = load_stock_data_vnquant(ticker, asset_type, start_date, end_date)
    else:
        df = load_stock_data_yf(ticker, asset_type, start_date, end_date)
    df_ta = add_technical_indicators_yf(df)
    signals = detect_signals(df_ta)

    news = get_news_for_ticker(ticker=ticker, asset_type=asset_type, look_back_days=look_back_days)

    # Create model instance
    model = genai.GenerativeModel('gemini-2.0-flash-exp')

    # Generate technical analysis response
    response_ta = model.generate_content([
        f"System: {system_prompt_ta}\n\nJust generate the REQUIRED content, DO NOT generate anything else. Only give the professional insights and analysis. DO NOT generate answer unnecessarily else. In Vietnamese.\n\n",
        f"You are a professional trader, analyst, businessman. Analyze professionally DO NOT explain or answer unnecessarily. Generate easy to read, professional insights, analysis, FOCUS DEEPLY on the GIVEN signals to help traders decide action with stock ticker {ticker}. Given: '{signals}'"
    ])

    # Generate news analysis response
    response_news = model.generate_content([
        f"System: {system_prompt_news}\n\nJust generate the REQUIRED content, DO NOT generate anything else. In Vietnamese.\n\n",
        f"You are a professional trader, analyst, businessman. Generate easy to read, professional insights and analysis to help traders decide action with stock ticker {ticker}. Given: '{news}'"
    ])

    # Generate final combined response
    response = model.generate_content([
        f"System: {system_prompt_news}\n\nJust generate the REQUIRED content, DO NOT generate anything else. Kết luận 1 trong những lựa chọn: MUA hoặc BÁN hoặc GIỮ. Có dẫn chứng chính xác. In Vietnamese.\n\n",
        f"You are a professional trader, analyst, businessman. Generate easy to read, professional insights, analysis WITH CONCISE REFERENCES to help traders decide action with stock ticker {ticker}. Given: '{response_news.text}' and '{response_ta.text}'"
    ])

    return response_ta, response_news, response

def get_insights_streaming(ticker: str, asset_type: str = 'stock', start_date: str = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'), end_date: str = datetime.now().strftime('%Y-%m-%d'), look_back_days: int=30):
    """
    Streaming version of get_insights that yields chunks in real-time.
    Returns a generator that yields Server-Sent Events formatted data.
    """
    import json
    
    ticker = ticker.upper()
    
    try:
        # Yield initial status
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải dữ liệu chứng khoán...', 'progress': 10})}\n\n"
        
        if asset_type == 'stock':
            df = load_stock_data_vnquant(ticker, asset_type, start_date, end_date)
        else:
            df = load_stock_data_yf(ticker, asset_type, start_date, end_date)
        df_ta = add_technical_indicators_yf(df)
        signals = detect_signals(df_ta)
        
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải tin tức...', 'progress': 20})}\n\n"
        
        news = get_news_for_ticker(ticker=ticker, asset_type=asset_type, look_back_days=30)
        
        # Create model instance
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Phase 1: Technical Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích kỹ thuật...', 'progress': 30})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'technical_analysis', 'title': 'Phân Tích Kỹ Thuật'})}\n\n"
        
        try:
            response_ta = model.generate_content([
                f"System: {system_prompt_ta}\n\nJust generate the REQUIRED content, DO NOT generate anything else. Only give the professional insights and analysis. DO NOT generate answer unnecessarily else. In Vietnamese.\n\n",
                f"You are a professional trader, analyst, businessman. Analyze professionally DO NOT explain or answer unnecessarily. Generate easy to read, professional insights, analysis, FOCUS DEEPLY on the GIVEN signals to help traders decide action with stock ticker {ticker}. Given: '{signals}'"
            ], stream=True)
            
            technical_content = ""
            for chunk in response_ta:
                if hasattr(chunk, 'text') and chunk.text:
                    technical_content += chunk.text
                    yield f"data: {json.dumps({'type': 'content', 'section': 'technical_analysis', 'text': chunk.text})}\n\n"
        except Exception as e:
            technical_content = f"Lỗi trong phân tích kỹ thuật: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'section': 'technical_analysis', 'message': technical_content})}\n\n"
        
        yield f"data: {json.dumps({'type': 'section_end', 'section': 'technical_analysis'})}\n\n"
        
        # Phase 2: News Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích tin tức...', 'progress': 60})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'news_analysis', 'title': 'Phân Tích Tin Tức'})}\n\n"
        
        try:
            response_news = model.generate_content([
                f"System: {system_prompt_news}\n\nJust generate the REQUIRED content, DO NOT generate anything else. In Vietnamese.\n\n",
                f"You are a professional trader, analyst, businessman. Generate easy to read, professional insights and analysis to help traders decide action with stock ticker {ticker}. Given: '{news}'"
            ], stream=True)
            
            news_content = ""
            for chunk in response_news:
                if hasattr(chunk, 'text') and chunk.text:
                    news_content += chunk.text
                    yield f"data: {json.dumps({'type': 'content', 'section': 'news_analysis', 'text': chunk.text})}\n\n"
        except Exception as e:
            news_content = f"Lỗi trong phân tích tin tức: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'section': 'news_analysis', 'message': news_content})}\n\n"
            
        yield f"data: {json.dumps({'type': 'section_end', 'section': 'news_analysis'})}\n\n"
        
        # Phase 3: Combined Analysis
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tạo phân tích tổng hợp...', 'progress': 80})}\n\n"
        yield f"data: {json.dumps({'type': 'section_start', 'section': 'combined_analysis', 'title': 'Phân Tích Tổng Hợp & Khuyến Nghị'})}\n\n"
        
        try:
            response_combined = model.generate_content([
                f"System: {system_prompt_news}\n\nJust generate the REQUIRED content, DO NOT generate anything else. Kết luận 1 trong những lựa chọn: MUA hoặc BÁN hoặc GIỮ. Có dẫn chứng chính xác. In Vietnamese.\n\n",
                f"You are a professional trader, analyst, businessman. Generate easy to read, professional insights, analysis WITH CONCISE REFERENCES to help traders decide action with stock ticker {ticker}. Given: '{news_content}' and '{technical_content}'"
            ], stream=True)
            
            for chunk in response_combined:
                if hasattr(chunk, 'text') and chunk.text:
                    yield f"data: {json.dumps({'type': 'content', 'section': 'combined_analysis', 'text': chunk.text})}\n\n"
        except Exception as e:
            combined_content = f"Lỗi trong phân tích tổng hợp: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'section': 'combined_analysis', 'message': combined_content})}\n\n"
            
        yield f"data: {json.dumps({'type': 'section_end', 'section': 'combined_analysis'})}\n\n"
        
        # Completion
        yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích hoàn tất!', 'progress': 100})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống: {str(e)}'})}\n\n"

def fetch_news_streaming(
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
    from datetime import datetime, timedelta
    
    symbol = symbol.upper().strip()
    
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
                yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tìm kiếm trên...', 'progress': 20})}\n\n"
                message = f'🔍 **Đang tìm kiếm tin tức về {symbol} trên...**\n\n'
                yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"

                # Create search query based on stock type
                if asset_type == 'stock':
                    # Remove .VN suffix for Vietnamese stocks
                    clean_symbol = symbol.replace('.VN', '')
                    search_query = f"tin tức cổ phiếu {clean_symbol} OR công ty {clean_symbol} OR mã {clean_symbol}"
                elif asset_type == 'crypto':
                    search_query = f"Important news for crypto currencies ticket {symbol}"

                google_news = fetch_google_news(
                    search_query,
                    datetime.now().strftime('%Y-%m-%d'),
                    look_back_days
                )
                
                if google_news:
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Đang xử lý kết quả...', 'progress': 40})}\n\n"
                    
                    # Parse format
                    from app_fastapi import parse_google_news_format
                    google_articles = parse_google_news_format(google_news, 'Google News')
                    
                    message = f'✅ **Tìm thấy {len(google_articles)} bài viết từ**\n\n'
                    yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"

                    # Stream individual articles
                    for i, article in enumerate(google_articles[:max_results//2]):
                        aggregated_news.append(article)
                        
                        # Stream article info
                        article_text = f"📰 **{article.get('title', 'No title')}**\\n"
                        article_text += f"📅 {article.get('date', 'No date')} | 🔗 {article.get('source', 'Unknown source')}\\n"
                        article_text += f"📊 Điểm liên quan: {article.get('relevance_score', 0):.1f}\\n\\n"
                        
                        yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': article_text})}\n\n"
                        
                        # Update progress
                        progress = min(40 + (i / len(google_articles[:max_results//2])) * 30, 70)
                        yield f"data: {json.dumps({'type': 'status', 'message': f'Đã xử lý {i+1}/{len(google_articles[:max_results//2])} bài viết...', 'progress': progress})}\n\n"
                        
                        # Small delay for streaming effect
                        import asyncio
                        import time
                        time.sleep(0.1)
                    
                    news_stats['sources_used'].append('google')
                    
                else:
                    message = '⚠️ **Không tìm thấy tin tức từ**\\n\\n'
                    yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"
                    
            except Exception as e:
                error_msg = f"❌ **Lỗi khi tìm kiếm:** {str(e)}\\n\\n"
                yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': error_msg})}\n\n"
        
        # Process and enhance news
        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang xử lý và phân tích tin tức...', 'progress': 75})}\n\n"
        
        # Remove duplicates based on title similarity
        if aggregated_news:
            message = '🔄 **Đang loại bỏ tin tức trùng lặp...**\\n\\n'
            yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"
            
            from app_fastapi import remove_duplicate_news
            original_count = len(aggregated_news)
            aggregated_news = remove_duplicate_news(aggregated_news)
            removed_count = original_count - len(aggregated_news)
            
            if removed_count > 0:
                message = f'✅ **Đã loại bỏ {removed_count} tin tức trùng lặp**\\n\\n'
                yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"
        
        # Add sentiment analysis
        if aggregated_news:
            message = '🧠 **Đang phân tích cảm xúc tin tức...**\\n\\n'
            yield f"data: {json.dumps({'type': 'content', 'section': 'news_collection', 'text': message})}\n\n"
            
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
        
        # Sort by relevance score and date
        if aggregated_news:
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
        
        # Stream final results
        if aggregated_news:
            for news in aggregated_news:
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
        else:
            message = '⚠️ **Không tìm thấy tin tức nào phù hợp.**\\n\\n'
            yield f"data: {json.dumps({'type': 'content', 'section': 'news_results', 'text': message})}\n\n"
        
        # End news results section
        yield f"data: {json.dumps({'type': 'section_end', 'section': 'news_results'})}\n\n"
        
        # Final response data
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
        print(final_response)
        
        # Completion
        yield f"data: {json.dumps({'type': 'complete', 'message': f'Hoàn tất! Tìm thấy {len(aggregated_news)} tin tức về {symbol}', 'progress': 100})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống: {str(e)}'})}\n\n"

if __name__ == "__main__":
    print(fetch_news_streaming("TCB"))