"""
Redis Configuration for Stock Data Caching
Cấu hình Redis Upstash cho cache dữ liệu cổ phiếu
"""

import redis
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class RedisConfig:
    """Redis configuration settings"""
    host: str
    port: int
    password: str
    ssl: bool = True
    decode_responses: bool = True
    socket_connect_timeout: int = 5
    socket_timeout: int = 5
    retry_on_timeout: bool = True
    health_check_interval: int = 30

class RedisManager:
    """Redis connection and data management"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.config = self._load_config()
        self._connect()
    
    def _load_config(self) -> RedisConfig:
        """Load Redis configuration from environment variables"""
        return RedisConfig(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv('REDIS_PASSWORD', ''),
            ssl=os.getenv('REDIS_SSL', 'true').lower() == 'true'
        )
    
    def _connect(self):
        """Establish Redis connection"""
        try:
            # Sử dụng REDIS_URL nếu có, fallback về cấu hình thủ công
            redis_url = os.getenv('REDIS_URL')
            self.client = redis.Redis.from_url(
                redis_url,
                decode_responses=self.config.decode_responses,
                socket_connect_timeout=self.config.socket_connect_timeout,
                socket_timeout=self.config.socket_timeout,
                retry_on_timeout=self.config.retry_on_timeout,
                health_check_interval=self.config.health_check_interval
            )
            logger.info("✅ Connected to Redis using REDIS_URL")
            # Test connection
            self.client.ping()
            logger.info("✅ Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.client = None
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        try:
            if self.client:
                self.client.ping()
                return True
        except:
            pass
        return False
    
    def reconnect(self):
        """Reconnect to Redis"""
        logger.info("🔄 Attempting to reconnect to Redis...")
        self._connect()
    
    # Stock data cache methods
    def get_stock_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached stock data"""
        if not self.is_connected():
            return None
        
        try:
            key = f"stock:{symbol.upper()}"
            data = self.client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error getting stock data for {symbol}: {e}")
        return None
    
    def set_stock_data(self, symbol: str, data: Dict[str, Any], ttl_seconds: int = 3600):
        """Cache stock data with TTL (default 1 hour)"""
        if not self.is_connected():
            return False
        
        try:
            key = f"stock:{symbol.upper()}"
            value = json.dumps(data, default=str)  # default=str for datetime serialization
            self.client.setex(key, ttl_seconds, value)
            
            # Add to cache index
            self.client.sadd("cached_symbols", symbol.upper())
            logger.debug(f"✅ Cached stock data for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error caching stock data for {symbol}: {e}")
            return False
    
    def get_cached_symbols(self) -> List[str]:
        """Get list of cached symbols"""
        if not self.is_connected():
            return []
        
        try:
            return list(self.client.smembers("cached_symbols"))
        except Exception as e:
            logger.error(f"Error getting cached symbols: {e}")
            return []
    
    def is_symbol_cached(self, symbol: str) -> bool:
        """Check if symbol is cached"""
        if not self.is_connected():
            return False
        
        try:
            return self.client.sismember("cached_symbols", symbol.upper())
        except Exception as e:
            logger.error(f"Error checking if {symbol} is cached: {e}")
            return False
    
    def set_last_full_fetch(self, timestamp: datetime):
        """Set timestamp of last full fetch"""
        if not self.is_connected():
            return
        
        try:
            self.client.set("last_full_fetch", timestamp.isoformat())
            logger.info(f"✅ Set last full fetch timestamp: {timestamp}")
        except Exception as e:
            logger.error(f"Error setting last full fetch: {e}")
    
    def get_last_full_fetch(self) -> Optional[datetime]:
        """Get timestamp of last full fetch"""
        if not self.is_connected():
            return None
        
        try:
            timestamp_str = self.client.get("last_full_fetch")
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.error(f"Error getting last full fetch: {e}")
        return None
    
    def clear_cache(self):
        """Clear all cached stock data"""
        if not self.is_connected():
            return
        
        try:
            # Get all cached symbols
            symbols = self.get_cached_symbols()
            
            # Delete stock data keys
            if symbols:
                keys_to_delete = [f"stock:{symbol}" for symbol in symbols]
                self.client.delete(*keys_to_delete)
            
            # Clear cache index
            self.client.delete("cached_symbols")
            logger.info(f"🗑️ Cleared cache for {len(symbols)} symbols")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.is_connected():
            return {"error": "Redis not connected"}
        
        try:
            cached_symbols = self.get_cached_symbols()
            last_fetch = self.get_last_full_fetch()
            
            # Get memory info
            memory_info = self.client.info('memory')
            
            return {
                "cached_symbols_count": len(cached_symbols),
                "cached_symbols": cached_symbols[:10],  # First 10 for preview
                "last_full_fetch": last_fetch.isoformat() if last_fetch else None,
                "memory_used": memory_info.get('used_memory_human', 'N/A'),
                "memory_peak": memory_info.get('used_memory_peak_human', 'N/A'),
                "redis_version": self.client.info('server').get('redis_version', 'N/A')
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
    
    def cleanup_expired_keys(self):
        """Cleanup any expired keys from cache index"""
        if not self.is_connected():
            return
        
        try:
            symbols = self.get_cached_symbols()
            expired_symbols = []
            
            for symbol in symbols:
                key = f"stock:{symbol}"
                if not self.client.exists(key):
                    expired_symbols.append(symbol)
            
            if expired_symbols:
                self.client.srem("cached_symbols", *expired_symbols)
                logger.info(f"🧹 Cleaned up {len(expired_symbols)} expired symbols from index")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired keys: {e}")

# Global Redis manager instance
redis_manager = RedisManager()

def get_redis_manager() -> RedisManager:
    """Get Redis manager instance"""
    return redis_manager
