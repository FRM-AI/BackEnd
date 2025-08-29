"""
Service Usage Tracking and Management System
Hệ thống theo dõi và quản lý sử dụng dịch vụ
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
from supabase_config import get_supabase_client
import json
import time
import logging
import functools

logger = logging.getLogger(__name__)

# Import wallet_manager at module level to avoid circular imports
try:
    from wallet_manager import wallet_manager
except ImportError:
    wallet_manager = None

# Pydantic Models
class ServiceUsage(BaseModel):
    id: str
    user_id: str
    service_type: str
    coins_spent: int
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[int] = None
    ip_address: Optional[str] = None
    created_at: datetime

class ServiceUsageRequest(BaseModel):
    service_type: str
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None

class ServiceStats(BaseModel):
    total_usage: int
    coins_spent: int
    avg_execution_time: Optional[float] = None
    by_service_type: Dict[str, Any]
    by_date: Dict[str, int]

class ServiceManager:
    def __init__(self):
        self.supabase = get_supabase_client(use_service_key=True)
        
        # Service types and their costs
        self.SERVICE_COSTS = {
            'stock_analysis': 5,
            'technical_analysis': 3,
            'portfolio_optimization': 10,
            'news_analysis': 2,
            'fundamental_scoring': 4,
            'ai_insights': 8,
            'alerts': 1
        }
        
        self.SERVICE_DESCRIPTIONS = {
            'stock_analysis': 'Phân tích cổ phiếu',
            'technical_analysis': 'Phân tích kỹ thuật',
            'portfolio_optimization': 'Tối ưu hóa danh mục',
            'news_analysis': 'Phân tích tin tức',
            'fundamental_scoring': 'Chấm điểm cơ bản',
            'ai_insights': 'Phân tích AI',
            'alerts': 'Cảnh báo'
        }
    
    async def get_service_cost(self, service_type: str) -> int:
        """Get service cost from database or default"""
        try:
            # Try to get from system settings first
            result = self.supabase.table('system_settings')\
                .select("value")\
                .eq('key', f'service_cost_{service_type}')\
                .execute()
            
            if result.data:
                return int(result.data[0]['value'])
            
            # Fall back to default costs
            return self.SERVICE_COSTS.get(service_type, 0)
            
        except Exception as e:
            logger.warning(f"Error getting service cost for {service_type}: {e}")
            return self.SERVICE_COSTS.get(service_type, 0)
    
    async def check_usage_limit(self, user_id: str, service_type: str) -> bool:
        """Check if user has exceeded daily usage limit"""
        try:
            # Get daily limit from settings
            limit_result = self.supabase.table('system_settings')\
                .select("value")\
                .eq('key', 'max_daily_service_usage')\
                .execute()
            
            daily_limit = int(limit_result.data[0]['value']) if limit_result.data else 100
            
            # Count today's usage
            today = datetime.now(timezone.utc).date().isoformat()
            
            usage_result = self.supabase.table('service_usage')\
                .select("id")\
                .eq('user_id', user_id)\
                .eq('service_type', service_type)\
                .gte('created_at', today)\
                .execute()
            
            current_usage = len(usage_result.data)
            
            return current_usage < daily_limit
            
        except Exception as e:
            logger.error(f"Error checking usage limit: {e}")
            return True  # Allow usage if we can't check
    
    async def track_service_usage(self, user_id: str, service_type: str, 
                                request_data: Optional[Dict] = None,
                                response_data: Optional[Dict] = None,
                                execution_time_ms: Optional[int] = None,
                                request: Optional[Request] = None) -> ServiceUsage:
        """Track service usage and deduct coins"""
        try:
            # Check if service type is valid
            if service_type not in self.SERVICE_COSTS:
                raise HTTPException(status_code=400, detail="Loại dịch vụ không hợp lệ")
            
            # Check usage limit
            if not await self.check_usage_limit(user_id, service_type):
                raise HTTPException(status_code=429, detail="Đã vượt quá giới hạn sử dụng hàng ngày")
            
            # Get service cost
            cost = await self.get_service_cost(service_type)
            actual_cost_deducted = 0
            
            # Check and deduct coins if needed
            if cost > 0 and wallet_manager is not None:
                try:
                    # Ensure wallet exists
                    wallet = await wallet_manager.ensure_wallet_exists(user_id)
                    
                    # If user has enough balance, deduct coins
                    if wallet.balance >= cost:
                        # Deduct coins
                        await wallet_manager.spend_coins(
                            user_id, cost, 'spend_service',
                            f"Sử dụng dịch vụ {self.SERVICE_DESCRIPTIONS.get(service_type, service_type)}",
                            'service', service_type
                        )
                        actual_cost_deducted = cost
                    else:
                        # Not enough balance - service still works but no coins deducted
                        logger.warning(f"User {user_id} doesn't have enough coins for {service_type} (needs {cost}, has {wallet.balance})")
                        actual_cost_deducted = 0
                except Exception as wallet_error:
                    logger.error(f"Wallet operation failed for user {user_id}: {wallet_error}")
                    # Continue without deducting coins
                    actual_cost_deducted = 0
            
            # Get IP address
            ip_address = None
            if request:
                ip_address = request.client.host if hasattr(request, 'client') else None
            
            # Ensure data is JSON serializable
            safe_request_data = serialize_request_data(request_data) if request_data else None
            safe_response_data = serialize_request_data(response_data) if response_data else None
            
            # Track usage
            usage_data = {
                "user_id": user_id,
                "service_type": service_type,
                "coins_spent": actual_cost_deducted,  # Use actual deducted amount
                "request_data": safe_request_data,
                "response_data": safe_response_data,
                "execution_time_ms": execution_time_ms,
                "ip_address": ip_address
            }
            
            result = self.supabase.table('service_usage').insert(usage_data).execute()
            
            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể ghi nhận sử dụng dịch vụ")
            
            return ServiceUsage(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Track service usage error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi ghi nhận sử dụng dịch vụ")
    
    async def get_user_usage_history(self, user_id: str, limit: int = 50, 
                                   offset: int = 0, service_type: Optional[str] = None,
                                   days: Optional[int] = None) -> List[ServiceUsage]:
        """Get user's service usage history"""
        try:
            query = self.supabase.table('service_usage').select("*").eq('user_id', user_id)
            
            if service_type:
                query = query.eq('service_type', service_type)
            
            if days:
                from_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                query = query.gte('created_at', from_date)
            
            result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
            
            return [ServiceUsage(**usage) for usage in result.data]
            
        except Exception as e:
            logger.error(f"Get user usage history error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy lịch sử sử dụng")
    
    async def get_user_usage_stats(self, user_id: str, days: int = 30) -> ServiceStats:
        """Get user's usage statistics"""
        try:
            from_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            result = self.supabase.table('service_usage')\
                .select("service_type, coins_spent, execution_time_ms, created_at")\
                .eq('user_id', user_id)\
                .gte('created_at', from_date)\
                .execute()
            
            usages = result.data
            
            # Calculate stats
            stats = {
                'total_usage': len(usages),
                'coins_spent': sum(usage['coins_spent'] for usage in usages),
                'avg_execution_time': None,
                'by_service_type': {},
                'by_date': {}
            }
            
            # Calculate average execution time
            execution_times = [usage['execution_time_ms'] for usage in usages if usage.get('execution_time_ms')]
            if execution_times:
                stats['avg_execution_time'] = sum(execution_times) / len(execution_times)
            
            # Group by service type
            for usage in usages:
                service_type = usage['service_type']
                if service_type not in stats['by_service_type']:
                    stats['by_service_type'][service_type] = {
                        'count': 0,
                        'coins_spent': 0,
                        'description': self.SERVICE_DESCRIPTIONS.get(service_type, service_type)
                    }
                
                stats['by_service_type'][service_type]['count'] += 1
                stats['by_service_type'][service_type]['coins_spent'] += usage['coins_spent']
            
            # Group by date
            for usage in usages:
                date_str = usage['created_at'][:10]  # Get YYYY-MM-DD
                stats['by_date'][date_str] = stats['by_date'].get(date_str, 0) + 1
            
            return ServiceStats(**stats)
            
        except Exception as e:
            logger.error(f"Get user usage stats error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy thống kê sử dụng")
    
    async def get_service_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get service analytics (admin only)"""
        try:
            from_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            result = self.supabase.table('service_usage')\
                .select("service_type, coins_spent, execution_time_ms, created_at, user_id")\
                .gte('created_at', from_date)\
                .execute()
            
            usages = result.data
            
            # Calculate analytics
            analytics = {
                'period_days': days,
                'total_usage': len(usages),
                'total_coins_spent': sum(usage['coins_spent'] for usage in usages),
                'unique_users': len(set(usage['user_id'] for usage in usages)),
                'by_service_type': {},
                'by_date': {},
                'avg_execution_time': None
            }
            
            # Calculate average execution time
            execution_times = [usage['execution_time_ms'] for usage in usages if usage.get('execution_time_ms')]
            if execution_times:
                analytics['avg_execution_time'] = sum(execution_times) / len(execution_times)
            
            # Group by service type
            for usage in usages:
                service_type = usage['service_type']
                if service_type not in analytics['by_service_type']:
                    analytics['by_service_type'][service_type] = {
                        'count': 0,
                        'coins_spent': 0,
                        'unique_users': set(),
                        'description': self.SERVICE_DESCRIPTIONS.get(service_type, service_type)
                    }
                
                analytics['by_service_type'][service_type]['count'] += 1
                analytics['by_service_type'][service_type]['coins_spent'] += usage['coins_spent']
                analytics['by_service_type'][service_type]['unique_users'].add(usage['user_id'])
            
            # Convert sets to counts
            for service_type in analytics['by_service_type']:
                analytics['by_service_type'][service_type]['unique_users'] = \
                    len(analytics['by_service_type'][service_type]['unique_users'])
            
            # Group by date
            for usage in usages:
                date_str = usage['created_at'][:10]  # Get YYYY-MM-DD
                if date_str not in analytics['by_date']:
                    analytics['by_date'][date_str] = {
                        'count': 0,
                        'coins_spent': 0,
                        'unique_users': set()
                    }
                
                analytics['by_date'][date_str]['count'] += 1
                analytics['by_date'][date_str]['coins_spent'] += usage['coins_spent']
                analytics['by_date'][date_str]['unique_users'].add(usage['user_id'])
            
            # Convert sets to counts for dates
            for date_str in analytics['by_date']:
                analytics['by_date'][date_str]['unique_users'] = \
                    len(analytics['by_date'][date_str]['unique_users'])
            
            return analytics
            
        except Exception as e:
            logger.error(f"Get service analytics error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy phân tích dịch vụ")

# Helper function to serialize data safely
def serialize_request_data(data):
    """Convert complex objects to JSON-serializable format"""
    if data is None:
        return None
    
    if isinstance(data, dict):
        serialized = {}
        for key, value in data.items():
            # Skip non-serializable objects
            if key in ['current_user', 'request']:
                continue
            
            try:
                # Try to serialize simple types
                if isinstance(value, (str, int, float, bool, type(None))):
                    serialized[key] = value
                elif isinstance(value, dict):
                    serialized[key] = serialize_request_data(value)
                elif isinstance(value, list):
                    serialized[key] = [serialize_request_data(item) for item in value]
                elif hasattr(value, 'dict'):  # Pydantic model
                    serialized[key] = value.dict()
                elif hasattr(value, '__dict__'):  # Object with attributes
                    # Only include basic attributes
                    obj_dict = {}
                    for attr_name, attr_value in value.__dict__.items():
                        if isinstance(attr_value, (str, int, float, bool, type(None))):
                            obj_dict[attr_name] = attr_value
                    if obj_dict:
                        serialized[key] = obj_dict
                else:
                    # Convert to string as fallback
                    serialized[key] = str(value)
            except Exception:
                # Skip problematic fields
                continue
        
        return serialized
    
    # For non-dict data, return None
    return None

# Decorator for tracking service usage
def track_service(service_type: str):
    """Decorator to automatically track service usage - FastAPI compatible"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Try to get user_id and request from arguments
            current_user = kwargs.get('current_user')
            user_id = None
            
            if current_user is not None and hasattr(current_user, 'id'):
                user_id = current_user.id
            elif isinstance(current_user, str):
                user_id = current_user
            
            request = kwargs.get('request')
            
            # Serialize request data safely
            safe_request_data = serialize_request_data(kwargs)
            
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Calculate execution time
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                # Track usage if user_id is available
                if user_id and isinstance(user_id, str):
                    await service_manager.track_service_usage(
                        user_id=user_id,
                        service_type=service_type,
                        request_data=safe_request_data,
                        response_data={"success": True},
                        execution_time_ms=execution_time_ms,
                        request=request
                    )
                
                return result
                
            except Exception as e:
                # Track failed usage
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                if user_id and isinstance(user_id, str):
                    try:
                        await service_manager.track_service_usage(
                            user_id=user_id,
                            service_type=service_type,
                            request_data=safe_request_data,
                            response_data={"success": False, "error": str(e)},
                            execution_time_ms=execution_time_ms,
                            request=request
                        )
                    except:
                        pass  # Don't fail if tracking fails
                
                raise e
        
        return wrapper
    return decorator

# Global service manager
service_manager = ServiceManager()
