"""
Stock Data Cache Manager
Quản lý cache dữ liệu cổ phiếu với Redis và APScheduler
"""

import asyncio
import logging
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import yfinance as yf
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from redis_config import get_redis_manager
from data_loader import load_stock_data_vnquant, load_stock_data_yf, load_stock_data_vn

logger = logging.getLogger(__name__)

class StockDataCacheManager:
    """Manages stock data caching with Redis and scheduled updates"""
    
    def __init__(self):
        self.redis_manager = get_redis_manager()
        self.scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Ho_Chi_Minh'))
        self.is_running = False
        
        # Batch configuration
        self.batch_size = 50  # Process 50 symbols at a time
        self.batch_delay = 1.0  # 1 second between batches
        self.max_retries = 3
        self.retry_delay = 2.0
        
    def start_scheduler(self):
        """Start the background scheduler (only for cache cleanup)"""
        if not self.is_running:
            try:
                # Only schedule cache cleanup every 6 hours - no automatic data fetching
                self.scheduler.add_job(
                    func=self.cleanup_cache,
                    trigger=CronTrigger(minute=0, hour="*/6"),
                    id='cache_cleanup',
                    name='Cache Cleanup',
                    replace_existing=True
                )
                
                self.scheduler.start()
                self.is_running = True
                logger.info("📅 Cache cleanup scheduler started (on-demand fetching only)")
                
            except Exception as e:
                logger.error(f"❌ Failed to start scheduler: {e}")
    
    def stop_scheduler(self):
        """Stop the background scheduler"""
        if self.is_running:
            try:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("🛑 Stock data cache scheduler stopped")
            except Exception as e:
                logger.error(f"❌ Failed to stop scheduler: {e}")
    
    async def check_and_initial_fetch(self):
        """Check if initial fetch is needed"""
        try:
            last_fetch = self.redis_manager.get_last_full_fetch()
            cached_symbols = self.redis_manager.get_cached_symbols()
            
            # If no recent fetch or very few symbols cached, do initial fetch
            if (not last_fetch or 
                (datetime.now() - last_fetch).total_seconds() > 86400 or 
                len(cached_symbols) < 50):
                
                logger.info("🚀 Running initial stock data fetch...")
                await asyncio.get_event_loop().run_in_executor(None, self.daily_full_fetch)
                
        except Exception as e:
            logger.error(f"❌ Error in initial fetch check: {e}")
    
    def daily_full_fetch(self):
        """Daily full fetch of all stock data"""
        logger.info("🔄 Starting daily full fetch of stock data...")
        start_time = time.time()
        
        try:
            # Clear old cache
            self.redis_manager.clear_cache()
            
            # Fetch Vietnamese stocks
            vn_success = self._batch_fetch_stocks(self.VN_STOCKS, "stock")
            
            # Fetch cryptocurrencies
            crypto_success = self._batch_fetch_stocks(self.CRYPTO_SYMBOLS, "crypto")
            
            # Set last full fetch timestamp
            self.redis_manager.set_last_full_fetch(datetime.now())
            
            total_time = time.time() - start_time
            logger.info(f"✅ Daily full fetch completed in {total_time:.2f}s")
            logger.info(f"📊 VN Stocks: {vn_success}/{len(self.VN_STOCKS)}, Crypto: {crypto_success}/{len(self.CRYPTO_SYMBOLS)}")
            
        except Exception as e:
            logger.error(f"❌ Error in daily full fetch: {e}")
    
    def _batch_fetch_stocks(self, symbols: List[str], asset_type: str) -> int:
        """Fetch stocks in batches to avoid rate limiting"""
        success_count = 0
        total_symbols = len(symbols)
        
        # Process in batches
        for i in range(0, total_symbols, self.batch_size):
            batch = symbols[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_symbols + self.batch_size - 1) // self.batch_size
            
            logger.info(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} symbols) for {asset_type}")
            
            try:
                # Fetch batch data
                batch_success = self._fetch_batch_with_retry(batch, asset_type)
                success_count += batch_success
                
                logger.info(f"✅ Batch {batch_num}: {batch_success}/{len(batch)} successful")
                
                # Delay between batches to avoid rate limiting
                if i + self.batch_size < total_symbols:
                    time.sleep(self.batch_delay)
                    
            except Exception as e:
                logger.error(f"❌ Error processing batch {batch_num}: {e}")
        
        return success_count
    
    def _fetch_batch_with_retry(self, symbols: List[str], asset_type: str) -> int:
        """Fetch a batch of symbols with retry logic"""
        for attempt in range(self.max_retries):
            try:
                if asset_type == "crypto":
                    return self._fetch_crypto_batch(symbols)
                else:
                    return self._fetch_vn_stock_batch(symbols)
                    
            except Exception as e:
                logger.warning(f"⚠️ Batch fetch attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"❌ All retry attempts failed for batch")
                    return 0
        
        return 0
    
    def _fetch_vn_stock_batch(self, symbols: List[str]) -> int:
        """Fetch Vietnamese stocks batch - VNQuant first, then Yahoo Finance fallback"""
        success_count = 0
        
        for symbol in symbols:
            try:
                # Try VNQuant first for Vietnamese stocks
                try:
                    df_vn = load_stock_data_vn(symbol)
                    if not df_vn.empty:
                        data = self._prepare_stock_data(df_vn, symbol, "stock")
                        if self.redis_manager.set_stock_data(symbol, data):
                            success_count += 1
                            continue
                    else:
                        raise Exception("No data from VNQuant")
                except Exception as vn_error:
                    logger.warning(f"⚠️ VNQuant failed for {symbol}: {vn_error}")
                    logger.info(f"🔄 Falling back to Yahoo Finance for {symbol}")
                    
                    # Fallback to Yahoo Finance
                    ticker_vn = symbol + ".VN"
                    try:
                        df = yf.download(ticker_vn, period="1y", interval="1d", progress=False)
                        
                        if not df.empty:
                            # Fix MultiIndex columns
                            if isinstance(df.columns, pd.MultiIndex):
                                df.columns = [col[0] for col in df.columns.values]
                            
                            data = self._prepare_stock_data(df, symbol, "stock")
                            
                            # Cache the data
                            if self.redis_manager.set_stock_data(symbol, data):
                                success_count += 1
                        else:
                            logger.warning(f"⚠️ Failed to fetch {symbol} from both VNQuant and Yahoo Finance")
                            
                    except Exception as yf_error:
                        logger.warning(f"⚠️ Yahoo Finance also failed for {symbol}: {yf_error}")
                        
            except Exception as e:
                logger.warning(f"⚠️ Error fetching VN stock {symbol}: {e}")
        
        return success_count
    
    def _fetch_crypto_batch(self, symbols: List[str]) -> int:
        """Fetch cryptocurrency batch"""
        success_count = 0
        
        # Prepare tickers for batch download
        tickers = [f"{symbol}-USD" for symbol in symbols]
        
        try:
            # Batch download from Yahoo Finance
            data = yf.download(tickers, period="1y", interval="1d", progress=False, group_by='ticker')
            
            if not data.empty:
                for symbol in symbols:
                    try:
                        ticker = f"{symbol}-USD"
                        
                        # Extract data for this symbol
                        if len(symbols) == 1:
                            symbol_data = data
                        else:
                            symbol_data = data[ticker]
                        
                        if not symbol_data.empty and not symbol_data.isna().all().all():
                            # Prepare and cache data
                            prepared_data = self._prepare_stock_data(symbol_data, symbol, "crypto")
                            
                            if self.redis_manager.set_stock_data(symbol, prepared_data):
                                success_count += 1
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Error processing crypto {symbol}: {e}")
            
        except Exception as e:
            logger.warning(f"⚠️ Error in crypto batch download: {e}")
            # Fallback to individual downloads
            for symbol in symbols:
                try:
                    df = yf.download(f"{symbol}-USD", period="1y", interval="1d", progress=False)
                    if not df.empty:
                        data = self._prepare_stock_data(df, symbol, "crypto")
                        if self.redis_manager.set_stock_data(symbol, data):
                            success_count += 1
                except:
                    pass
        
        return success_count
    
    def _prepare_stock_data(self, df: pd.DataFrame, symbol: str, asset_type: str) -> Dict[str, Any]:
        """Prepare stock data for caching with API-compatible structure"""
        # Reset index to make Date a column
        if 'Date' not in df.columns:
            df = df.reset_index()
        
        # Fix MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns.values]
        
        # Standardize column names to match API expectations
        column_mapping = {
            'Adj Close': 'Close',  # Use Adj Close as Close if available
            'date': 'Date',
            'open': 'Open',
            'high': 'High', 
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]
        
        # Ensure required columns exist
        required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_cols:
            if col not in df.columns:
                if col == 'Date':
                    df[col] = pd.date_range(start='2024-01-01', periods=len(df), freq='D')
                else:
                    df[col] = 0
        
        # Convert Date to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df['Date']):
            df['Date'] = pd.to_datetime(df['Date'])
        
        # Convert to USD equivalent for crypto if needed
        if asset_type == "crypto":
            try:
                # Get USD/VND rate for conversion
                usd_vnd_rate = yf.Ticker("USDVND=X").history(period="1d", interval="1m")["Close"].iloc[-1]
                price_columns = ['Open', 'High', 'Low', 'Close']
                for col in price_columns:
                    if col in df.columns:
                        df[col] = df[col] * usd_vnd_rate
            except:
                pass  # If conversion fails, keep USD values
        
        # Clean data and convert to JSON-serializable format
        df = df.replace([float('inf'), float('-inf')], None)
        df = df.fillna(0)
        
        # Sort by date ascending (oldest first)
        df = df.sort_values('Date')
        
        # Prepare chart data in the exact format expected by the API
        chart_data = []
        for _, row in df.iterrows():
            try:
                # Convert timestamp to Unix timestamp (seconds) for chart compatibility
                timestamp = int(pd.Timestamp(row['Date']).timestamp())
                
                open_price = float(row['Open']) if not pd.isna(row['Open']) else 0
                high_price = float(row['High']) if not pd.isna(row['High']) else 0
                low_price = float(row['Low']) if not pd.isna(row['Low']) else 0
                close_price = float(row['Close']) if not pd.isna(row['Close']) else 0
                volume = int(row['Volume']) if not pd.isna(row['Volume']) else 0
                
                # Skip invalid data points
                if all(price > 0 for price in [open_price, high_price, low_price, close_price]):
                    chart_data.append({
                        'time': timestamp,
                        'open': round(open_price, 2),
                        'high': round(high_price, 2),
                        'low': round(low_price, 2),
                        'close': round(close_price, 2),
                        'volume': volume
                    })
            except (ValueError, TypeError):
                continue
        
        # Calculate summary statistics
        latest_data = chart_data[-1] if chart_data else None
        price_change = 0
        price_change_percent = 0
        
        if len(chart_data) >= 2:
            current_price = latest_data['close']
            previous_price = chart_data[-2]['close']
            price_change = current_price - previous_price
            price_change_percent = (price_change / previous_price) * 100 if previous_price != 0 else 0
        
        # Market info based on asset type
        market_info = {
            'stock': {
                'name': 'Thị trường chứng khoán Việt Nam',
                'note': 'Hỗ trợ tất cả mã cổ phiếu niêm yết tại HOSE, HNX, UPCOM',
                'currency': 'VND',
                'timezone': 'Asia/Ho_Chi_Minh'
            },
            'crypto': {
                'name': 'Thị trường tiền điện tử',
                'note': 'Hỗ trợ tất cả mã crypto phổ biến (BTC, ETH, BNB, ADA, SOL...)',
                'currency': 'VND (quy đổi từ USD)',
                'timezone': 'UTC'
            }
        }.get(asset_type, {
            'name': 'Thị trường tài chính',
            'note': 'Hỗ trợ cổ phiếu Việt Nam và crypto quốc tế',
            'currency': 'VND',
            'timezone': 'Asia/Ho_Chi_Minh'
        })
        
        return {
            'symbol': symbol.upper(),
            'asset_type': asset_type,
            'market_info': market_info,
            'chart_data': chart_data,
            'summary': {
                'total_records': len(chart_data),
                'date_range': {
                    'start': chart_data[0]['time'] if chart_data else None,
                    'end': chart_data[-1]['time'] if chart_data else None
                },
                'latest_price': latest_data['close'] if latest_data else 0,
                'price_change': round(price_change, 2),
                'price_change_percent': round(price_change_percent, 2),
                'volume': latest_data['volume'] if latest_data else 0
            },
            'supported_assets': {
                'vietnam_stocks': 'Tất cả mã cổ phiếu Việt Nam (VD: VCB, FPT, VIC, MSN, HPG...)',
                'crypto': 'Tất cả mã crypto phổ biến (VD: BTC, ETH, BNB, ADA, SOL, DOGE...)',
                'note': '💡 Nhập chính xác mã cổ phiếu VN hoặc ký hiệu crypto để xem biểu đồ'
            },
            'cache_info': {
                'last_updated': datetime.now().isoformat(),
                'data_points': len(chart_data),
                'source': 'redis_cache'
            }
        }
    
    def get_stock_data(self, symbol: str, asset_type: str = "stock") -> Optional[Dict[str, Any]]:
        """Get stock data from cache or fetch on-demand"""
        symbol = symbol.upper()
        
        # Try to get from cache first
        cached_data = self.redis_manager.get_stock_data(symbol)
        if cached_data:
            logger.debug(f"📦 Cache hit for {symbol}")
            return cached_data
        
        # Cache miss - fetch on-demand
        logger.info(f"🔍 Cache miss for {symbol}, fetching on-demand...")
        return self._fetch_on_demand(symbol, asset_type)
    
    def _fetch_on_demand(self, symbol: str, asset_type: str) -> Optional[Dict[str, Any]]:
        """Fetch single symbol on-demand with fallback logic"""
        try:
            # Set TTL to 1 hour (3600 seconds) as requested
            ttl = 3600
            
            # Fetch data using the updated load_stock_data_vnquant with VNQuant-first logic
            from data_loader import load_stock_data_vnquant, load_stock_data_yf
            
            if asset_type == "crypto":
                df = load_stock_data_yf(symbol, asset_type="crypto", start="2023-01-01", end=datetime.now().strftime('%Y-%m-%d'))
            else:
                # For stocks, use VNQuant first, then Yahoo Finance fallback
                df = load_stock_data_vnquant(symbol, asset_type="stock", start="2023-01-01", end=datetime.now().strftime('%Y-%m-%d'))
            
            if df is not None and not df.empty:
                # Prepare and cache data
                data = self._prepare_stock_data(df, symbol, asset_type)
                
                if self.redis_manager.set_stock_data(symbol, data, ttl):
                    logger.info(f"✅ Successfully fetched and cached {symbol} on-demand (TTL: 1 hour)")
                    return data
            
            logger.warning(f"⚠️ No data available for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error fetching {symbol} on-demand: {e}")
            return None
    
    def cleanup_cache(self):
        """Cleanup expired cache entries"""
        try:
            self.redis_manager.cleanup_expired_keys()
            logger.info("🧹 Cache cleanup completed")
        except Exception as e:
            logger.error(f"❌ Error in cache cleanup: {e}")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status and statistics"""
        try:
            stats = self.redis_manager.get_cache_stats()
            
            # Add scheduler status
            stats.update({
                'scheduler_running': self.is_running,
                'next_full_fetch': None,
                'batch_size': self.batch_size,
                'total_symbols_configured': len(self.VN_STOCKS) + len(self.CRYPTO_SYMBOLS)
            })
            
            # Get next scheduled run
            if self.is_running:
                try:
                    job = self.scheduler.get_job('daily_stock_fetch')
                    if job:
                        stats['next_full_fetch'] = job.next_run_time.isoformat()
                except:
                    pass
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting cache status: {e}")
            return {'error': str(e)}

# Global cache manager instance
cache_manager = StockDataCacheManager()

def get_cache_manager() -> StockDataCacheManager:
    """Get cache manager instance"""
    return cache_manager
