"""
Error Logging and Management System
Hệ thống quản lý lỗi và logging
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, Request
from supabase_config import get_supabase_client
import logging
import traceback
import json

logger = logging.getLogger(__name__)

# Pydantic Models
class ErrorLog(BaseModel):
    id: str
    user_id: Optional[str] = None
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    request_url: Optional[str] = None
    request_method: Optional[str] = None
    request_data: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

class ErrorLogCreate(BaseModel):
    user_id: Optional[str] = None
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    request_url: Optional[str] = None
    request_method: Optional[str] = None
    request_data: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class ErrorStats(BaseModel):
    total_errors: int
    by_type: Dict[str, int]
    by_date: Dict[str, int]
    recent_errors: List[ErrorLog]

class ErrorManager:
    def __init__(self):
        self.supabase = get_supabase_client()
        
        # Error types
        self.ERROR_TYPES = {
            'authentication': 'Lỗi xác thực',
            'authorization': 'Lỗi phân quyền',
            'validation': 'Lỗi validation',
            'database': 'Lỗi cơ sở dữ liệu',
            'external_api': 'Lỗi API ngoài',
            'business_logic': 'Lỗi logic nghiệp vụ',
            'system': 'Lỗi hệ thống',
            'network': 'Lỗi mạng',
            'timeout': 'Lỗi timeout',
            'unknown': 'Lỗi không xác định'
        }
    
    async def log_error(self, error_data: ErrorLogCreate) -> ErrorLog:
        """Log error to database"""
        try:
            result = self.supabase.table('error_logs').insert(error_data.dict()).execute()
            
            if not result.data:
                logger.error("Failed to insert error log to database")
                return None
            
            return ErrorLog(**result.data[0])
            
        except Exception as e:
            # Don't fail the main operation if error logging fails
            logger.error(f"Error logging failed: {e}")
            return None
    
    async def log_exception(self, exception: Exception, request: Optional[Request] = None,
                          user_id: Optional[str] = None, error_type: str = 'unknown') -> Optional[ErrorLog]:
        """Log exception with context"""
        try:
            # Extract request information
            request_url = str(request.url) if request else None
            request_method = request.method if request else None
            ip_address = request.client.host if request and hasattr(request, 'client') else None
            user_agent = request.headers.get('user-agent') if request else None
            
            # Extract request data (be careful with sensitive data)
            request_data = None
            if request and hasattr(request, '_body'):
                try:
                    body = await request.body()
                    if body:
                        request_data = json.loads(body.decode())
                        # Remove sensitive fields
                        if isinstance(request_data, dict):
                            for sensitive_field in ['password', 'token', 'secret', 'key']:
                                if sensitive_field in request_data:
                                    request_data[sensitive_field] = '***'
                except:
                    request_data = None
            
            error_log_data = ErrorLogCreate(
                user_id=user_id,
                error_type=error_type,
                error_message=str(exception),
                stack_trace=traceback.format_exc(),
                request_url=request_url,
                request_method=request_method,
                request_data=request_data,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            return await self.log_error(error_log_data)
            
        except Exception as e:
            logger.error(f"Exception logging failed: {e}")
            return None
    
    async def get_error_logs(self, limit: int = 50, offset: int = 0,
                           error_type: Optional[str] = None,
                           user_id: Optional[str] = None,
                           days: Optional[int] = None) -> List[ErrorLog]:
        """Get error logs with filters"""
        try:
            query = self.supabase.table('error_logs').select("*")
            
            if error_type:
                query = query.eq('error_type', error_type)
            
            if user_id:
                query = query.eq('user_id', user_id)
            
            if days:
                from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
                query = query.gte('created_at', from_date)
            
            result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
            
            return [ErrorLog(**log) for log in result.data]
            
        except Exception as e:
            logger.error(f"Get error logs failed: {e}")
            return []
    
    async def get_error_stats(self, days: int = 30) -> ErrorStats:
        """Get error statistics"""
        try:
            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            result = self.supabase.table('error_logs')\
                .select("error_type, created_at")\
                .gte('created_at', from_date)\
                .execute()
            
            errors = result.data
            
            # Calculate stats
            stats = {
                'total_errors': len(errors),
                'by_type': {},
                'by_date': {}
            }
            
            # Group by type
            for error in errors:
                error_type = error['error_type']
                stats['by_type'][error_type] = stats['by_type'].get(error_type, 0) + 1
            
            # Group by date
            for error in errors:
                date_str = error['created_at'][:10]  # Get YYYY-MM-DD
                stats['by_date'][date_str] = stats['by_date'].get(date_str, 0) + 1
            
            # Get recent errors
            recent_errors = await self.get_error_logs(limit=10)
            
            return ErrorStats(
                total_errors=stats['total_errors'],
                by_type=stats['by_type'],
                by_date=stats['by_date'],
                recent_errors=recent_errors
            )
            
        except Exception as e:
            logger.error(f"Get error stats failed: {e}")
            return ErrorStats(
                total_errors=0,
                by_type={},
                by_date={},
                recent_errors=[]
            )
    
    async def clear_old_errors(self, days_to_keep: int = 90) -> int:
        """Clear old error logs"""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days_to_keep)).isoformat()
            
            result = self.supabase.table('error_logs')\
                .delete()\
                .lt('created_at', cutoff_date)\
                .execute()
            
            deleted_count = len(result.data) if result.data else 0
            logger.info(f"Cleared {deleted_count} old error logs")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Clear old errors failed: {e}")
            return 0
    
    def get_error_type(self, exception: Exception) -> str:
        """Determine error type from exception"""
        exception_type = type(exception).__name__
        
        if 'Auth' in exception_type or 'Login' in exception_type:
            return 'authentication'
        elif 'Permission' in exception_type or 'Forbidden' in exception_type:
            return 'authorization'
        elif 'Validation' in exception_type or 'ValueError' in exception_type:
            return 'validation'
        elif 'Database' in exception_type or 'SQL' in exception_type:
            return 'database'
        elif 'Connection' in exception_type or 'Timeout' in exception_type:
            return 'network'
        elif 'HTTP' in exception_type:
            return 'external_api'
        else:
            return 'unknown'

# Custom logging formatter
class CustomFormatter(logging.Formatter):
    """Custom formatter for application logs"""
    
    def __init__(self):
        super().__init__()
        
        # Color codes
        self.COLORS = {
            logging.DEBUG: '\033[36m',     # Cyan
            logging.INFO: '\033[32m',      # Green
            logging.WARNING: '\033[33m',   # Yellow
            logging.ERROR: '\033[31m',     # Red
            logging.CRITICAL: '\033[35m',  # Magenta
        }
        self.RESET = '\033[0m'
        
        # Formats
        self.FORMATS = {
            logging.DEBUG: "%(asctime)s - %(name)s - [DEBUG] - %(message)s",
            logging.INFO: "%(asctime)s - %(name)s - [INFO] - %(message)s",
            logging.WARNING: "%(asctime)s - %(name)s - [WARNING] - %(message)s",
            logging.ERROR: "%(asctime)s - %(name)s - [ERROR] - %(message)s",
            logging.CRITICAL: "%(asctime)s - %(name)s - [CRITICAL] - %(message)s",
        }
    
    def format(self, record):
        # Get format and color for this log level
        log_format = self.FORMATS.get(record.levelno, self.FORMATS[logging.INFO])
        color = self.COLORS.get(record.levelno, '')
        
        # Create formatter
        formatter = logging.Formatter(f"{color}{log_format}{self.RESET}")
        
        return formatter.format(record)

def setup_application_logging():
    """Setup application-wide logging"""
    import os
    
    # Get configuration
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_to_file = os.getenv('LOG_TO_FILE', 'True').lower() == 'true'
    log_file_path = os.getenv('LOG_FILE_PATH', 'logs/frm-ai.log')
    
    # Create logs directory
    if log_to_file:
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler with custom formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomFormatter())
    root_logger.addHandler(console_handler)
    
    # File handler
    if log_to_file:
        file_handler = logging.FileHandler(log_file_path)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Set specific loggers
    loggers_config = {
        'uvicorn': logging.WARNING,
        'uvicorn.error': logging.INFO,
        'uvicorn.access': logging.WARNING,
        'fastapi': logging.INFO,
        'supabase': logging.WARNING,
        'httpx': logging.WARNING,
        'urllib3': logging.WARNING
    }
    
    for logger_name, level in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)

# Global error manager
error_manager = ErrorManager()

# Exception handler decorator
def handle_exceptions(error_type: str = 'unknown'):
    """Decorator to automatically log exceptions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Try to get user_id and request from arguments
                user_id = None
                request = None
                
                for arg in args:
                    if hasattr(arg, 'id'):  # User object
                        user_id = arg.id
                    elif hasattr(arg, 'url'):  # Request object
                        request = arg
                
                for key, value in kwargs.items():
                    if key == 'current_user' and hasattr(value, 'id'):
                        user_id = value.id
                    elif key == 'request' and hasattr(value, 'url'):
                        request = value
                
                # Log the exception
                await error_manager.log_exception(e, request, user_id, error_type)
                
                # Re-raise the exception
                raise e
        
        return wrapper
    return decorator
