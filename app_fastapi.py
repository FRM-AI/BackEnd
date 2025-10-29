"""
FastAPI Application for Financial Risk Management (FRM-AI)
Ứng dụng FastAPI hoàn chỉnh với Supabase Database Integration - Production Optimized
"""

from fastapi import FastAPI, HTTPException, Request, Depends, status, WebSocket, WebSocketDisconnect, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Optional, Any
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys
import math
import logging
import time

import asyncio

# Import custom modules
import re
from difflib import SequenceMatcher
import uvicorn
import logging

from pathlib import Path

# Redis and Cache Management
from redis_config import get_redis_manager
from stock_cache_manager import get_cache_manager

# Get the directory where this script is located
CURRENT_DIR = Path(__file__).parent
TEMPLATES_DIR = CURRENT_DIR.parent / "templates"  # Go up one level to FRM-AI/templates
STATIC_DIR = CURRENT_DIR / "static"

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('frm_ai.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Performance monitoring
class PerformanceMonitoring:
    def __init__(self):
        self.request_count = 0
        self.total_response_time = 0
        self.start_time = time.time()
    
    def log_request(self, response_time: float):
        self.request_count += 1
        self.total_response_time += response_time
    
    def get_stats(self):
        uptime = time.time() - self.start_time
        avg_response_time = self.total_response_time / max(self.request_count, 1)
        return {
            "uptime": uptime,
            "total_requests": self.request_count,
            "average_response_time": avg_response_time,
            "requests_per_minute": (self.request_count / max(uptime / 60, 1))
        }

performance_monitor = PerformanceMonitoring()

# Ensure templates directory exists
if not TEMPLATES_DIR.exists():
    logger.error(f"Templates directory not found: {TEMPLATES_DIR}")
    # Fallback to relative path
    TEMPLATES_DIR = Path("templates")

logger.info(f"Templates directory: {TEMPLATES_DIR.absolute()}")
logger.info(f"Templates directory exists: {TEMPLATES_DIR.exists()}")

# Add the additionalModules to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'additionalModules'))

# Import database and auth components
from supabase_config import get_supabase_client, test_supabase_connection
from auth_manager import (
    auth_manager, get_current_user, get_optional_user, require_admin,
    UserRegister, UserLogin, UserUpdate, ChangePassword, User, UserWithWallet
)
from wallet_manager import (
    wallet_manager, WalletInfo, WalletTransaction, TransactionRequest, 
    TransferRequest
)
from package_manager import (
    package_manager, Package, UserPackage, PackageCreate, PackageUpdate
)
from service_manager import service_manager, track_service, check_balance_and_track, check_balance_and_track_streaming
from notification_manager import (
    notification_manager, Notification, NotificationCreate, 
    BulkNotificationCreate
)
from database import database_manager
from insights_history_manager import (
    insights_history_manager, InsightHistory, InsightHistoryCreate
)

from data_loader import load_stock_data_vn, load_stock_data_vnquant, load_stock_data_yf, load_stock_data_cached, get_stock_data_for_api
from feature_engineering import add_technical_indicators_vnquant, add_technical_indicators_yf
from technical_analysis import detect_signals
from fundamental_scoring_vn import score_stock, rank_stocks
from portfolio_optimization import optimize_portfolio, calculate_manual_portfolio
from alert import send_alert
from news_analysis import (
    get_insights_streaming, 
    get_technical_analysis_streaming,
    get_news_analysis_streaming, 
    get_proprietary_trading_analysis_streaming,
    get_intraday_match_analysis_streaming,
    get_foreign_trading_analysis_streaming,
    get_shareholder_trading_analysis_streaming
)
from fetch_cafef import (
    get_shareholder_data, get_price_history, get_foreign_trading_data,
    get_proprietary_trading_data, get_match_price, get_realtime_price,
    get_company_info, get_leadership, get_subsidiaries, get_financial_reports,
    get_company_profile, get_finance_data, get_global_indices
)
# from stock_analysis import analyze_stock

# Additional Pydantic Models for new features
class LoginResponse(BaseModel):
    user: UserWithWallet
    token: str
    message: str

class DashboardStats(BaseModel):
    users: Dict[str, int]
    packages: Dict[str, int]
    wallet: Dict[str, float]
    service_usage: Dict[str, int]

# Enhanced Pydantic Models for existing functionality
class StockDataRequest(BaseModel):
    symbol: str = Field(default="VCB", description="Mã cổ phiếu")
    asset_type: str = Field(default="stock", description="Loại tài sản: stock, crypto")
    start_date: str = Field(default="2024-01-01", description="Ngày bắt đầu (YYYY-MM-DD)")
    end_date: str = Field(default="2024-12-31", description="Ngày kết thúc (YYYY-MM-DD)")

class TechnicalSignalsRequest(BaseModel):
    symbol: str = Field(default="VCB", description="Mã cổ phiếu")
    asset_type: str = Field(default="stock", description="Loại tài sản: stock, crypto")

class FundamentalScoreRequest(BaseModel):
    tickers: List[str] = Field(default=["VCB.VN", "BID.VN", "CTG.VN"], description="Danh sách mã cổ phiếu")

class NewsRequest(BaseModel):
    symbol: str = Field(default="VCB", description="Mã cổ phiếu")
    asset_type: str = Field(default="stock", description="Loại tài sản: stock, crypto")
    pages: int = Field(default=2, ge=1, le=10, description="Số trang tin tức")
    look_back_days: int = Field(default=30, ge=1, le=365, description="Số ngày quay lại")
    news_sources: List[str] = Field(default=["google"], description="Nguồn tin tức")
    max_results: int = Field(default=50, ge=10, le=200, description="Số kết quả tối đa")

class AlertRequest(BaseModel):
    email: str = Field(..., description="Email nhận cảnh báo")
    subject: str = Field(default="Stock Alert", description="Tiêu đề email")
    signals: List[str] = Field(default=[], description="Danh sách tín hiệu")

class PortfolioOptimizationRequest(BaseModel):
    symbols: List[str] = Field(default=["VCB", "BID", "CTG", "MBB", "TCB"], description="Danh sách mã cổ phiếu")
    asset_type: str = Field(default="stock", description="Loại tài sản: stock, crypto")
    start_date: str = Field(default=None, description="Ngày bắt đầu (YYYY-MM-DD)")
    end_date: str = Field(default=None, description="Ngày kết thúc (YYYY-MM-DD)")
    investment_amount: float = Field(default=1000000000, ge=1000000, description="Số tiền đầu tư (VND)")

class ManualPortfolioRequest(BaseModel):
    manual_weights: Dict[str, float] = Field(..., description="Tỷ trọng thủ công (%)")
    asset_type: str = Field(default="stock", description="Loại tài sản: stock, crypto")
    start_date: str = Field(default="2024-01-01", description="Ngày bắt đầu (YYYY-MM-DD)")
    end_date: str = Field(default="2024-12-31", description="Ngày kết thúc (YYYY-MM-DD)")
    investment_amount: float = Field(default=1000000000, ge=1000000, description="Số tiền đầu tư (VND)")

class InsightsRequest(BaseModel):
    ticker: str = Field(default="VCB", description="Mã cổ phiếu")
    asset_type: str = Field(default="stock", description="Loại tài sản: stock, crypto")
    start_date: str = Field(default=None, description="Ngày bắt đầu (YYYY-MM-DD)")
    end_date: str = Field(default=None, description="Ngày kết thúc (YYYY-MM-DD)")
    look_back_days: int = Field(default=30, ge=1, le=365, description="Số ngày quay lại")

class StockAnalysisRequest(BaseModel):
    symbol: str = Field(..., description="Mã cổ phiếu")

class CreateConversationRequest(BaseModel):
    participant_ids: List[str] = Field(..., description="List of participant user IDs")
    name: Optional[str] = Field(None, description="Conversation name (for group chats)")

class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000, description="Message content")
    message_type: str = Field("text", description="Type of message: text, image, file")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional message metadata")

class MarkMessagesAsReadRequest(BaseModel):
    message_id: Optional[str] = Field(None, description="Mark up to this message as read")
    start_date: str = Field(default="2011-01-01", description="Ngày bắt đầu (YYYY-MM-DD)")
    forecast_periods: int = Field(default=30, ge=1, le=365, description="Số ngày dự báo")

# Pydantic Models for CafeF APIs
class ShareholderDataRequest(BaseModel):
    symbol: str = Field(..., description="Mã cổ phiếu")
    start_date: Optional[str] = Field(None, description="Ngày bắt đầu (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Ngày kết thúc (YYYY-MM-DD)")
    page_index: int = Field(default=1, ge=1, description="Chỉ số trang")
    page_size: int = Field(default=14, ge=1, le=100, description="Kích thước trang")

class PriceHistoryRequest(BaseModel):
    symbol: str = Field(..., description="Mã cổ phiếu")
    start_date: Optional[str] = Field(None, description="Ngày bắt đầu (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Ngày kết thúc (YYYY-MM-DD)")
    page_index: int = Field(default=1, ge=1, description="Chỉ số trang")
    page_size: int = Field(default=14, ge=1, le=100, description="Kích thước trang")

class ForeignTradingRequest(BaseModel):
    symbol: str = Field(..., description="Mã cổ phiếu")
    start_date: Optional[str] = Field(None, description="Ngày bắt đầu (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Ngày kết thúc (YYYY-MM-DD)")
    page_index: int = Field(default=1, ge=1, description="Chỉ số trang")
    page_size: int = Field(default=14, ge=1, le=100, description="Kích thước trang")

class ProprietaryTradingRequest(BaseModel):
    symbol: str = Field(..., description="Mã cổ phiếu")
    start_date: Optional[str] = Field(None, description="Ngày bắt đầu (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Ngày kết thúc (YYYY-MM-DD)")
    page_index: int = Field(default=1, ge=1, description="Chỉ số trang")
    page_size: int = Field(default=14, ge=1, le=100, description="Kích thước trang")

class MatchPriceRequest(BaseModel):
    symbol: str = Field(..., description="Mã cổ phiếu")
    date: str = Field(..., description="Ngày giao dịch (YYYY-MM-DD hoặc YYYYMMDD)")

class CompanyProfileRequest(BaseModel):
    symbol: str = Field(..., description="Mã cổ phiếu")
    type_id: int = Field(default=1, description="Loại hồ sơ công ty")
    page_index: int = Field(default=0, ge=0, description="Chỉ số trang")
    page_size: int = Field(default=4, ge=1, le=100, description="Kích thước trang")

# Utility Functions (enhanced with better error handling)
def clean_dataframe_for_json(df):
    """Clean DataFrame to ensure JSON serialization"""
    # Replace all NaN, inf, -inf with None
    df = df.replace([np.inf, -np.inf], None)
    df = df.where(pd.notna(df), None)
    
    # Convert to records and clean any remaining problematic values
    records = df.to_dict('records')
    
    for record in records:
        for key, value in record.items():
            if isinstance(value, (np.integer, np.floating)):
                if np.isnan(value) or np.isinf(value):
                    record[key] = None
                else:
                    record[key] = float(value) if isinstance(value, np.floating) else int(value)
            elif pd.isna(value):
                record[key] = None
    
    return records

def calculate_relevance_score(title, symbol):
    """Calculate relevance score for news article based on title and symbol"""
    if not title:
        return 0
    
    title_lower = title.lower()
    symbol_clean = symbol.replace('.VN', '').lower()
    
    # Base score
    score = 0
    
    # Direct symbol match
    if symbol_clean in title_lower:
        score += 10
    
    # Partial symbol match
    if any(char in title_lower for char in symbol_clean):
        score += 5
    
    # Keywords that increase relevance
    high_relevance_keywords = [
        'cổ phiếu', 'stock', 'shares', 'công ty', 'company', 'doanh nghiệp',
        'tài chính', 'financial', 'kinh doanh', 'business', 'đầu tư', 'investment',
        'lợi nhuận', 'profit', 'doanh thu', 'revenue', 'tăng trưởng', 'growth'
    ]
    
    for keyword in high_relevance_keywords:
        if keyword in title_lower:
            score += 2
    
    # Financial impact keywords
    impact_keywords = [
        'tăng', 'giảm', 'tăng trưởng', 'suy giảm', 'lỗ', 'lãi',
        'rise', 'fall', 'up', 'down', 'gain', 'loss', 'profit'
    ]
    
    for keyword in impact_keywords:
        if keyword in title_lower:
            score += 1
    
    return min(score, 20)  # Cap at 20

def parse_google_news_format(google_news_text, source):
    """Parse Google News format into structured articles with enhanced link and date extraction"""
    articles = []
    
    if not google_news_text:
        return articles
    
    # Split by news sections
    sections = google_news_text.split('### ')
    
    for section in sections[1:]:  # Skip first empty section
        try:
            lines = section.strip().split('\n')
            if len(lines) >= 2:
                # Extract title, source, date, and link from first line
                title_line = lines[0].strip()
                
                # Enhanced regex to capture source, date, and link
                enhanced_match = re.match(r'(.*?)\s*\(source:\s*(.*?),\s*date:\s*(.*?),\s*link:\s*(.*?)\)', title_line)
                
                if enhanced_match:
                    title = enhanced_match.group(1).strip()
                    news_source = enhanced_match.group(2).strip()
                    news_date = enhanced_match.group(3).strip()
                    news_link = enhanced_match.group(4).strip()
                else:
                    # Fallback to simpler format
                    simple_match = re.match(r'(.*?)\s*\(source:\s*(.*?)\)', title_line)
                    if simple_match:
                        title = simple_match.group(1).strip()
                        news_source = simple_match.group(2).strip()
                        news_date = 'Gần đây'
                        news_link = '#'
                    else:
                        title = title_line
                        news_source = source
                        news_date = 'Gần đây'
                        news_link = '#'
                
                # Extract snippet from remaining lines
                snippet = '\n'.join(lines[1:]).strip()
                
                # Clean up the link (remove any extra characters)
                if news_link and news_link != '#':
                    news_link = news_link.strip()
                    # Ensure link is properly formatted
                    if not news_link.startswith('http'):
                        news_link = '#'
                
                articles.append({
                    'title': title,
                    'snippet': snippet,
                    'content': snippet,  # Add content field for consistency
                    'source': news_source,
                    'link': news_link,
                    'url': news_link,  # Add url field for frontend compatibility
                    'date': news_date,
                    'published_at': news_date,  # Add published_at for consistency
                    'relevance_score': calculate_relevance_score(title, ''),
                    'id': f"news-{len(articles)}"  # Add unique ID
                })
        except Exception as e:
            logger.error(f"Error parsing news section: {e}")
            continue
    
    return articles

def remove_duplicate_news(news_list):
    """Remove duplicate news articles based on title similarity"""
    if not news_list:
        return news_list
    
    unique_news = []
    seen_titles = []
    
    for article in news_list:
        title = article.get('title', '')
        if not title:
            continue
            
        # Check for similar titles
        is_duplicate = False
        for seen_title in seen_titles:
            similarity = SequenceMatcher(None, title.lower(), seen_title.lower()).ratio()
            if similarity > 0.8:  # 80% similarity threshold
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_news.append(article)
            seen_titles.append(title)
    
    return unique_news

def enhance_news_with_sentiment(news_list):
    """Add sentiment analysis to news articles"""
    # This could be enhanced with actual sentiment analysis
    # For now, we'll add a simple keyword-based sentiment
    positive_keywords = ['tăng', 'tăng trưởng', 'lợi nhuận', 'thành công', 'rise', 'gain', 'profit', 'success']
    negative_keywords = ['giảm', 'suy giảm', 'lỗ', 'khó khăn', 'fall', 'loss', 'decline', 'trouble']
    
    for article in news_list:
        title_lower = article.get('title', '').lower()
        snippet_lower = article.get('snippet', '').lower()
        content = title_lower + ' ' + snippet_lower
        
        positive_count = sum(1 for keyword in positive_keywords if keyword in content)
        negative_count = sum(1 for keyword in negative_keywords if keyword in content)
        
        if positive_count > negative_count:
            article['sentiment'] = 'positive'
        elif negative_count > positive_count:
            article['sentiment'] = 'negative'
        else:
            article['sentiment'] = 'neutral'
        
        article['sentiment_score'] = positive_count - negative_count
    
    return news_list

def parse_cookies_from_websocket(websocket: WebSocket) -> Dict[str, str]:
    """Parse cookies from WebSocket request headers"""
    cookies = {}
    try:
        headers = websocket.headers
        cookie_header = headers.get('cookie', '')
        
        if cookie_header:
            # Parse cookie string: "key1=value1; key2=value2"
            for cookie_part in cookie_header.split(';'):
                cookie_part = cookie_part.strip()
                if '=' in cookie_part:
                    key, value = cookie_part.split('=', 1)
                    cookies[key.strip()] = value.strip()
        
        logger.debug(f"Parsed cookies from WebSocket: {list(cookies.keys())}")
        return cookies
        
    except Exception as e:
        logger.error(f"Error parsing cookies from WebSocket: {e}")
        return {}

# FastAPI Application
app = FastAPI(
    title="FRM-AI Financial Risk Management",
    description="Hệ thống quản lý rủi ro tài chính với AI - Supabase Integration",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# =====================================
# REMOVED: HTML Templates (Now using Next.js Frontend)
# templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# =====================================

# =====================================
# MIDDLEWARE CONFIGURATION
# =====================================

from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import time

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://frmai.org",
        "https://www.frmai.org",
        "https://api.frmai.org",  # ✅ add backend subdomain itself
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://0.0.0.0:8000",
        "file://",
        "null"
    ],
    allow_credentials=True,
    allow_methods=["*"],  # ✅ allow all, Safari sometimes preflights uncommon verbs
    allow_headers=["*"],  # ✅ let Safari send Authorization + custom headers
    expose_headers=[
        "X-Total-Count",
        "X-Page-Count", 
        "X-Rate-Limit-Limit",
        "X-Rate-Limit-Remaining",
        "X-Rate-Limit-Reset"
    ]
)

# Add GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add trusted host middleware for production security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "*.frmai.org",
        "localhost",
        "127.0.0.1",
        "*.vercel.app"
    ]
)

# Performance monitoring middleware
@app.middleware("http")
async def performance_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Log performance metrics
    performance_monitor.log_request(process_time)
    
    # Add performance headers
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-Count"] = str(performance_monitor.request_count)
    
    # Log slow requests
    if process_time > 2.0:
        logger.warning(f"Slow request: {request.method} {request.url} took {process_time:.2f}s")
    
    return response

# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response

# Performance monitoring middleware
@app.middleware("http")
async def performance_monitoring(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Add performance headers
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-API-Version"] = "3.0.0"
    
    # Add cache headers for static-like content
    if request.url.path.startswith("/api/packages") or \
       request.url.path.startswith("/api/system-settings"):
        response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes
    
    # Add no-cache headers for user-specific content
    if request.url.path.startswith("/api/auth") or \
       request.url.path.startswith("/api/wallet") or \
       request.url.path.startswith("/api/notifications"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    
    return response

# Test database connection on startup
@app.on_event("startup")
async def startup_event():
    """Test database connection and initialize services on startup"""
    logger.info("Starting FRM-AI application...")
    try:
        if test_supabase_connection():
            logger.info("✅ Supabase connection successful")
        else:
            logger.error("❌ Supabase connection failed")
        
        # Initialize cache manager and start scheduler
        cache_manager = get_cache_manager()
        cache_manager.start_scheduler()
        logger.info("✅ Stock data cache manager initialized and scheduled")
        
        # Test Redis connection
        redis_manager = get_redis_manager()
        if redis_manager.is_connected():
            logger.info("✅ Redis connection successful")
        else:
            logger.error("❌ Redis connection failed")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Shutting down FRM-AI application...")
    try:
        # Stop cache manager scheduler
        cache_manager = get_cache_manager()
        cache_manager.stop_scheduler()
        logger.info("✅ Cache manager scheduler stopped")
        
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

# ================================
# AUTHENTICATION ROUTES
# ================================

@app.post("/api/auth/register")
async def register(user_data: UserRegister, response: Response):
    """Đăng ký tài khoản mới"""
    result = await auth_manager.register_user(user_data)

    # Tạo ví cho user vừa đăng ký
    await wallet_manager.ensure_wallet_exists(result["user"].id)
    
    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=result["session_id"],
        httponly=True,
        max_age=60*60*24,  # 24 hours
        samesite="none",
        secure=True,  # Set to True in production with HTTPS
        path='/'
    )
    
    # Remove session_id from response body for security
    return {
        "user": result["user"],
        "message": result["message"]
    }

@app.post("/api/auth/login")
async def login(login_data: UserLogin, response: Response):
    """Đăng nhập"""
    result = await auth_manager.login_user(login_data)
    
    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=result["session_id"],
        httponly=True,
        max_age=60*60*24,  # 24 hours
        samesite="none",
        secure=True,  # Set to True in production with HTTPS
        path='/'
    )
    
    # Remove session_id from response body for security
    return {
        "user": result["user"],
        "message": result["message"]
    }

@app.post("/api/auth/logout")
async def logout(response: Response, current_user: Optional[UserWithWallet] = Depends(get_optional_user)):
    """Đăng xuất"""
    # If user is logged in, invalidate their session
    if current_user:
        # Get session_id from cookie and delete from database
        # This would be handled by the session deletion logic
        pass
    
    # Delete session cookie
    response.delete_cookie(
        key="session_id",
        path="/",
        secure=True,
        samesite="none"
    )
    return {"message": "Đã đăng xuất"}

@app.get("/api/auth/me", response_model=UserWithWallet)
async def get_current_user_info(current_user: UserWithWallet = Depends(get_current_user)):
    """Lấy thông tin người dùng hiện tại"""
    return current_user

@app.put("/api/auth/profile", response_model=User)
async def update_profile(
    update_data: UserUpdate,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Cập nhật thông tin cá nhân"""
    return await auth_manager.update_user(current_user.id, update_data)

@app.post("/api/auth/change-password")
async def change_password(
    password_data: ChangePassword,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Đổi mật khẩu"""
    return await auth_manager.change_password(current_user.id, password_data)

# ================================
# WALLET ROUTES
# ================================

@app.get("/api/wallet", response_model=WalletInfo)
async def get_wallet_info(current_user: UserWithWallet = Depends(get_current_user)):
    """Lấy thông tin ví"""
    return await wallet_manager.get_wallet(current_user.id)

@app.get("/api/wallet/transactions", response_model=List[WalletTransaction])
async def get_wallet_transactions(
    limit: int = 50,
    offset: int = 0,
    transaction_type: Optional[str] = None,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Lấy lịch sử giao dịch"""
    return await wallet_manager.get_transactions(
        current_user.id, limit, offset, transaction_type
    )

@app.post("/api/wallet/transfer")
async def transfer_coins(
    transfer_data: TransferRequest,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Chuyển tiền cho người dùng khác"""
    return await wallet_manager.transfer_coins(
        current_user.id, transfer_data.recipient_email, 
        transfer_data.amount, transfer_data.description
    )

@app.get("/api/wallet/stats")
async def get_wallet_stats(
    days: int = 30,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Lấy thống kê ví"""
    return await wallet_manager.get_wallet_stats(current_user.id, days)

# ================================
# PACKAGE ROUTES
# ================================

@app.get("/api/packages", response_model=List[Package])
async def get_packages(include_inactive: bool = False):
    """Lấy danh sách gói dịch vụ"""
    return await package_manager.get_all_packages(include_inactive)

@app.get("/api/packages/{package_id}", response_model=Package)
async def get_package(package_id: int):
    """Lấy thông tin gói dịch vụ"""
    return await package_manager.get_package(package_id)

@app.post("/api/packages/{package_id}/purchase")
async def purchase_package(
    package_id: int,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Mua gói dịch vụ"""
    return await package_manager.purchase_package(current_user.id, package_id)

@app.get("/api/my-packages", response_model=List[UserPackage])
async def get_my_packages(
    status: Optional[str] = None,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Lấy danh sách gói đã mua"""
    return await package_manager.get_user_packages(current_user.id, status)

@app.post("/api/packages/{user_package_id}/cancel")
async def cancel_my_package(
    user_package_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Hủy gói dịch vụ"""
    return await package_manager.cancel_package(current_user.id, user_package_id)

# ================================
# NOTIFICATION ROUTES
# ================================

@app.get("/api/notifications", response_model=List[Notification])
async def get_notifications(
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Lấy danh sách thông báo"""
    return await notification_manager.get_user_notifications(
        current_user.id, limit, offset, unread_only
    )

@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Đánh dấu thông báo đã đọc"""
    return await notification_manager.mark_as_read(current_user.id, notification_id)

@app.post("/api/notifications/mark-all-read")
async def mark_all_notifications_read(
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Đánh dấu tất cả thông báo đã đọc"""
    return await notification_manager.mark_all_as_read(current_user.id)

@app.delete("/api/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Xóa thông báo"""
    return await notification_manager.delete_notification(current_user.id, notification_id)

@app.get("/api/notifications/unread-count")
async def get_unread_notifications_count(
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Lấy số lượng thông báo chưa đọc"""
    count = await notification_manager.get_unread_count(current_user.id)
    return {"unread_count": count}

# ================================
# SERVICE USAGE ROUTES
# ================================

@app.get("/api/service-usage/history")
async def get_service_usage_history(
    limit: int = 50,
    offset: int = 0,
    service_type: Optional[str] = None,
    days: Optional[int] = None,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Lấy lịch sử sử dụng dịch vụ"""
    return await service_manager.get_user_usage_history(
        current_user.id, limit, offset, service_type, days
    )

@app.get("/api/service-usage/stats")
async def get_service_usage_stats(
    days: int = 30,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Lấy thống kê sử dụng dịch vụ"""
    return await service_manager.get_user_usage_stats(current_user.id, days)

@app.get("/api/service-usage/check-balance/{service_type}")
async def check_service_balance(
    service_type: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Kiểm tra số dư cho dịch vụ cụ thể (chỉ dành cho dashboard)"""
    return await service_manager.check_balance_for_service(current_user.id, service_type)

# ================================
# ADMIN ROUTES
# ================================

@app.get("/api/admin/dashboard", response_model=DashboardStats)
async def get_admin_dashboard(admin_user: UserWithWallet = Depends(require_admin)):
    """Dashboard thống kê cho admin"""
    return await database_manager.get_dashboard_stats()

@app.get("/api/admin/financial-summary")
async def get_financial_summary(
    days: int = 30,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Tóm tắt tài chính"""
    return await database_manager.get_financial_summary(days)

@app.post("/api/admin/packages", response_model=Package)
async def create_package_admin(
    package_data: PackageCreate,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Tạo gói dịch vụ mới (admin)"""
    return await package_manager.create_package(package_data)

@app.put("/api/admin/packages/{package_id}", response_model=Package)
async def update_package_admin(
    package_id: int,
    update_data: PackageUpdate,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Cập nhật gói dịch vụ (admin)"""
    return await package_manager.update_package(package_id, update_data)

@app.post("/api/admin/notifications/broadcast")
async def broadcast_notification(
    notification_data: BulkNotificationCreate,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Gửi thông báo hàng loạt (admin)"""
    return await notification_manager.create_bulk_notifications(notification_data)

@app.get("/api/admin/service-analytics")
async def get_service_analytics_admin(
    days: int = 30,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Phân tích dịch vụ (admin)"""
    return await service_manager.get_service_analytics(days)

@app.post("/api/admin/wallet/{user_id}/add-coins")
async def admin_add_coins(
    user_id: str,
    amount: float,
    description: str,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Admin thêm coins cho user"""
    return await wallet_manager.add_coins(
        user_id, amount, 'admin_adjustment', 
        f"Admin adjustment: {description}"
    )

@app.post("/api/admin/cleanup")
async def cleanup_old_data(
    days_to_keep: int = 365,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Dọn dẹp dữ liệu cũ (admin)"""
    return await database_manager.cleanup_old_data(days_to_keep)

# ================================
# DATA EXPORT ROUTES (GDPR)
# ================================

@app.get("/api/user/export-data")
async def export_user_data(current_user: UserWithWallet = Depends(get_current_user)):
    """Xuất tất cả dữ liệu của user (GDPR)"""
    return await database_manager.export_user_data(current_user.id)

@app.delete("/api/user/delete-account")
async def delete_user_account(current_user: UserWithWallet = Depends(get_current_user)):
    """Xóa tài khoản và tất cả dữ liệu (GDPR)"""
    success = await database_manager.delete_user_data(current_user.id)
    if success:
        return {"message": "Tài khoản đã được xóa thành công"}
    else:
        raise HTTPException(status_code=500, detail="Lỗi khi xóa tài khoản")

# ================================
# INSIGHTS HISTORY ROUTES
# ================================

@app.get("/api/insights-history", response_model=List[InsightHistory])
async def get_insights_history(
    limit: int = 50,
    offset: int = 0,
    analysis_type: Optional[str] = None,
    ticker: Optional[str] = None,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """
    Lấy lịch sử phân tích insights của user
    
    - **limit**: Số lượng kết quả tối đa (default: 50)
    - **offset**: Vị trí bắt đầu (default: 0)
    - **analysis_type**: Lọc theo loại phân tích (technical_analysis, news_analysis, etc.)
    - **ticker**: Lọc theo mã cổ phiếu
    """
    return await insights_history_manager.get_user_insights(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        analysis_type=analysis_type,
        ticker=ticker
    )

@app.get("/api/insights-history/{insight_id}", response_model=InsightHistory)
async def get_insight_detail(
    insight_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """
    Lấy chi tiết một phân tích theo ID
    """
    insight = await insights_history_manager.get_insight_by_id(
        user_id=current_user.id,
        insight_id=insight_id
    )
    
    if not insight:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân tích")
    
    return insight

@app.delete("/api/insights-history/{insight_id}")
async def delete_insight(
    insight_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """
    Xóa một phân tích
    """
    return await insights_history_manager.delete_insight(
        user_id=current_user.id,
        insight_id=insight_id
    )

@app.delete("/api/insights-history")
async def delete_all_insights(
    current_user: UserWithWallet = Depends(get_current_user)
):
    """
    Xóa tất cả lịch sử phân tích
    """
    return await insights_history_manager.delete_all_user_insights(
        user_id=current_user.id
    )

@app.get("/api/insights-history/stats")
async def get_insights_stats(
    current_user: UserWithWallet = Depends(get_current_user)
):
    """
    Lấy thống kê lịch sử phân tích
    """
    return await insights_history_manager.get_insights_stats(
        user_id=current_user.id
    )
    
# ================================
# ENHANCED FINANCIAL ANALYSIS API ROUTES
# ================================

@app.post("/api/stock_data")
@check_balance_and_track("stock_analysis")
async def get_stock_data(
    request_data: StockDataRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Lấy dữ liệu giá cổ phiếu và chỉ báo kỹ thuật cho biểu đồ chuyên nghiệp (với Redis cache)"""
    try:
        # Get data directly from cache in API format
        cached_result = get_stock_data_for_api(request_data.symbol, request_data.asset_type)
        
        if cached_result:
            # Update authentication status
            cached_result['authenticated'] = current_user is not None
            cached_result['generated_at'] = datetime.now().isoformat()
            
            # Filter by date range if specified
            if request_data.start_date or request_data.end_date:
                chart_data = cached_result.get('chart_data', [])
                if chart_data:
                    start_timestamp = int(pd.to_datetime(request_data.start_date).timestamp()) if request_data.start_date else 0
                    end_timestamp = int(pd.to_datetime(request_data.end_date).timestamp()) if request_data.end_date else float('inf')
                    
                    filtered_data = [
                        item for item in chart_data 
                        if start_timestamp <= item.get('time', 0) <= end_timestamp
                    ]
                    
                    cached_result['chart_data'] = filtered_data
                    cached_result['summary']['total_records'] = len(filtered_data)
                    
                    if filtered_data:
                        cached_result['summary']['date_range'] = {
                            'start': filtered_data[0]['time'],
                            'end': filtered_data[-1]['time']
                        }
                        cached_result['summary']['latest_price'] = filtered_data[-1]['close']
                        cached_result['summary']['volume'] = filtered_data[-1]['volume']
            
            return cached_result
        
        # Fallback to original method if cache fails
        if request_data.asset_type == 'stock':
            df = load_stock_data_vnquant(
                request_data.symbol, 
                request_data.asset_type, 
                "2000-01-01", 
                datetime.now().strftime('%Y-%m-%d')
            )
        else:
            df = load_stock_data_yf(
                request_data.symbol, 
                request_data.asset_type, 
                "2000-01-01", 
                datetime.now().strftime('%Y-%m-%d')
            )
        
        if df is None or df.empty:
            raise HTTPException(
                status_code=404, 
                detail=f"Không tìm thấy dữ liệu cho mã {request_data.symbol}. " +
                       "Hệ thống chỉ hỗ trợ cổ phiếu Việt Nam (VD: VCB, FPT, VIC) và crypto (VD: BTC, ETH, BNB)."
            )

        # Ensure required columns exist and rename for chart compatibility
        required_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        
        # Check if all required columns exist
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=500, 
                detail=f"Dữ liệu thiếu các cột: {missing_columns}"
            )

        # Format data for lightweight-charts
        chart_data = []
        for _, row in df.iterrows():
            # Convert timestamp to Unix timestamp (seconds)
            if pd.isna(row['Date']):
                continue
                
            timestamp = int(pd.Timestamp(row['Date']).timestamp())
            
            # Ensure all price values are valid numbers
            try:
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

        # Sort by timestamp
        chart_data.sort(key=lambda x: x['time'])
        
        # Get latest price info for summary
        latest_data = chart_data[-1] if chart_data else None
        price_change = 0
        price_change_percent = 0
        
        if len(chart_data) >= 2:
            current_price = latest_data['close']
            previous_price = chart_data[-2]['close']
            price_change = current_price - previous_price
            price_change_percent = (price_change / previous_price) * 100 if previous_price != 0 else 0

        # Determine market info based on asset type
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
        }.get(request_data.asset_type, {
            'name': 'Thị trường tài chính',
            'note': 'Hỗ trợ cổ phiếu Việt Nam và crypto quốc tế',
            'currency': 'VND',
            'timezone': 'Asia/Ho_Chi_Minh'
        })
        
        return {
            'success': True,
            'symbol': request_data.symbol.upper(),
            'asset_type': request_data.asset_type,
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
            'authenticated': current_user is not None,
            'generated_at': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_stock_data: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Lỗi khi tải dữ liệu. Vui lòng kiểm tra mã cổ phiếu/crypto và thử lại. " +
                   "Hệ thống chỉ hỗ trợ cổ phiếu Việt Nam và crypto quốc tế."
        )

@app.post("/api/technical_signals")
@check_balance_and_track("technical_signals")
async def get_technical_signals(
    request_data: TechnicalSignalsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Phát hiện tín hiệu kỹ thuật với Redis cache"""
    try:
        # Create cache key for technical signals
        cache_key = f"technical_signals:{request_data.symbol.upper()}:{request_data.asset_type}"
        
        try:
            # Try to get cached signals from Redis
            redis_manager = get_redis_manager()
            cached_signals = await redis_manager.get_json(cache_key)
            
            if cached_signals:
                logger.info(f"Returning cached technical signals for {request_data.symbol}")
                cached_signals['from_cache'] = True
                cached_signals['cached_at'] = cached_signals.get('generated_at', datetime.now().isoformat())
                cached_signals['generated_at'] = datetime.now().isoformat()
                return cached_signals
                
        except Exception as cache_err:
            logger.warning(f"Cache error for technical signals: {cache_err}")
        
        # Load and analyze data using cached function
        df = load_stock_data_cached(request_data.symbol, request_data.asset_type)
        
        if df is None or df.empty:
            raise HTTPException(
                status_code=404, 
                detail=f"Không tìm thấy dữ liệu cho mã {request_data.symbol}"
            )
        
        df = add_technical_indicators_yf(df)
        
        # Detect signals
        signals = detect_signals(df)
        
        # Clean signals data if it contains DataFrames or problematic values
        if isinstance(signals, dict):
            for key, value in signals.items():
                if isinstance(value, pd.DataFrame):
                    signals[key] = clean_dataframe_for_json(value)
        
        result = {
            'success': True,
            'signals': signals,
            'symbol': request_data.symbol,
            'generated_at': datetime.now().isoformat(),
            'authenticated': current_user is not None,
            'from_cache': False
        }
        
        # Cache the results for 6 hours
        try:
            redis_manager = get_redis_manager()
            await redis_manager.set_json(cache_key, result, expire=21600)  # 6 hours
            logger.info(f"Cached technical signals for {request_data.symbol}")
        except Exception as cache_err:
            logger.warning(f"Failed to cache technical signals: {cache_err}")
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.post("/api/fundamental_score")
@check_balance_and_track("fundamental_scoring")
async def get_fundamental_score(
    request_data: FundamentalScoreRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Tính điểm cơ bản cho nhiều cổ phiếu"""
    try:
        # Score multiple stocks
        results = []
        for ticker in request_data.tickers:
            try:
                score_result = score_stock(ticker)
                results.append(score_result)
            except Exception as e:
                results.append({
                    'ticker': ticker,
                    'score': 0,
                    'error': str(e)
                })
        
        return {
            'success': True,
            'results': results,
            'total_stocks': len(request_data.tickers),
            'evaluated_at': datetime.now().isoformat(),
            'authenticated': current_user is not None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.post("/api/news")
@check_balance_and_track_streaming("get_news")
async def get_news(
    request_data: NewsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Lấy tin tức về cổ phiếu từ nhiều nguồn với streaming response và Redis cache"""
    
    # Check if client wants streaming response (default: true)
    use_streaming = request.headers.get("Accept", "").find("text/event-stream") != -1 or \
                   request.query_params.get("stream", "true").lower() == "true"
    
    if use_streaming:
        # Return streaming response with cache
        async def generate_news():
            try:
                # Validate inputs
                if not request_data.symbol:
                    yield f"data: {{\"type\": \"error\", \"message\": \"Mã tài sản là bắt buộc\"}}\n\n"
                    return
                
                # Create cache key for news
                cache_key = f"news:{request_data.symbol.upper()}:{request_data.asset_type}:{request_data.look_back_days}:{request_data.pages}:{request_data.max_results}"
                
                try:
                    # Try to get cached news from Redis
                    redis_manager = get_redis_manager()
                    cached_news = await redis_manager.get_json(cache_key)
                    
                    if cached_news and cached_news.get('data'):
                        # Send cached news data
                        metadata = {
                            'symbol': request_data.symbol.upper(),
                            'generated_at': datetime.now().isoformat(),
                            'look_back_days': request_data.look_back_days,
                            'pages': request_data.pages,
                            'max_results': request_data.max_results,
                            'news_sources': request_data.news_sources,
                            'authenticated': current_user is not None,
                            'from_cache': True
                        }
                        
                        # Send metadata first
                        yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"
                        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải tin tức từ cache...', 'progress': 10})}\n\n"
                        yield f"data: {json.dumps({'type': 'section_start', 'section': 'news_collection', 'title': f'Thu Thập Tin Tức - {request_data.symbol.upper()}'})}\n\n"
                        
                        # Stream cached news results
                        news_data = cached_news['data']
                        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang chuẩn bị kết quả từ cache...', 'progress': 90})}\n\n"
                        yield f"data: {json.dumps({'type': 'section_start', 'section': 'news_results', 'title': f'Kết Quả Tin Tức - {len(news_data)} bài viết'})}\n\n"
                        
                        # Stream each news item
                        for i, news_item in enumerate(news_data):
                            news_text = f"📰 **{news_item.get('title', 'Không có tiêu đề')}**\\n\\n"
                            news_text += f"📅 {news_item.get('date', 'Không có ngày')} | 🏢 {news_item.get('source', 'Không rõ nguồn')}\\n\\n"
                            news_text += f"{news_item.get('snippet', 'Không có mô tả')}\\n\\n"
                            if news_item.get('link'):
                                news_text += f"🔗 [Đọc thêm]({news_item['link']})\\n\\n"
                            news_text += "---\\n\\n"
                            
                            yield f"data: {json.dumps({'type': 'content', 'section': 'news_results', 'text': news_text})}\n\n"
                            
                            # Add delay between items
                            
                            await asyncio.sleep(0.1)
                        
                        yield f"data: {json.dumps({'type': 'section_end', 'section': 'news_results'})}\n\n"
                        yield f"data: {json.dumps({'type': 'final_data', 'data': cached_news})}\n\n"
                        yield f"data: {json.dumps({'type': 'complete', 'message': f'Hoàn tất! Tìm thấy {len(news_data)} tin tức về {request_data.symbol.upper()} từ cache', 'progress': 100})}\n\n"
                        return
                        
                except Exception as cache_err:
                    logger.warning(f"Cache error for news: {cache_err}")
                    yield f"data: {{\"type\": \"status\", \"message\": \"Cache không khả dụng, đang tìm kiếm tin tức mới...\", \"progress\": 5}}\n\n"
                
                # Import streaming function
                try:
                    from news_analysis import fetch_news_streaming
                except ImportError as import_err:
                    logger.error(f"Cannot import fetch_news_streaming: {import_err}")
                    yield f"data: {{\"type\": \"error\", \"message\": \"News analysis module not available\"}}\n\n"
                    return
                
                # Initialize metadata for new fetch
                metadata = {
                    'symbol': request_data.symbol.upper(),
                    'generated_at': datetime.now().isoformat(),
                    'look_back_days': request_data.look_back_days,
                    'pages': request_data.pages,
                    'max_results': request_data.max_results,
                    'news_sources': request_data.news_sources,
                    'authenticated': current_user is not None,
                    'from_cache': False
                }
                
                # Send metadata first
                yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"
                
                # Variables to collect final data for caching
                final_news_data = None
                
                # Generate streaming news and collect final data
                for chunk in fetch_news_streaming(
                    symbol=request_data.symbol.upper(),
                    asset_type=request_data.asset_type,
                    look_back_days=request_data.look_back_days,
                    pages=request_data.pages,
                    max_results=request_data.max_results,
                    news_sources=request_data.news_sources
                ):
                    yield chunk
                    
                    # Parse chunk to get final data for caching
                    try:
                        if chunk.startswith("data: "):
                            chunk_data = json.loads(chunk[6:].strip())
                            if chunk_data.get('type') == 'final_data':
                                final_news_data = chunk_data.get('data')
                    except:
                        pass
                    
                    # Add small delay to make streaming more visible
                    
                    await asyncio.sleep(0.01)
                
                # Cache the results for 6 hours
                if final_news_data:
                    try:
                        redis_manager = get_redis_manager()
                        await redis_manager.set_json(cache_key, final_news_data, expire=21600)  # 6 hours
                        logger.info(f"Cached news for {request_data.symbol}")
                    except Exception as cache_err:
                        logger.warning(f"Failed to cache news: {cache_err}")
                    
            except Exception as e:
                logger.error(f"Error in streaming news: {e}")
                yield f"data: {{\"type\": \"error\", \"message\": \"Server xử lý lỗi. Vui lòng thử lại.\"}}\n\n"
        
        return StreamingResponse(
            generate_news(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
    
    else:
        # Legacy non-streaming response for backward compatibility
        try:
            # Validate inputs
            if not request_data.symbol:
                raise HTTPException(status_code=400, detail="Mã cổ phiếu là bắt buộc")
            
            # Clean and format symbol
            symbol = request_data.symbol.upper().strip()
            
            # Initialize news aggregation
            aggregated_news = []
            news_stats = {
                'total_articles': 0,
                'sources_used': [],
                'date_range': {
                    'from': (datetime.now() - timedelta(days=request_data.look_back_days)).strftime('%Y-%m-%d'),
                    'to': datetime.now().strftime('%Y-%m-%d')
                },
                'processing_time': 0
            }
            
            start_time = datetime.now()
            
            # Google News (universal source)
            if 'google' in request_data.news_sources:
                try:
                    # Import fetch_google_news with error handling
                    try:
                        from news_analysis import fetch_google_news
                    except ImportError as import_err:
                        logger.error(f"Cannot import fetch_google_news: {import_err}")
                        raise HTTPException(status_code=500, detail="News analysis module not available")
                    
                    # Create search query based on stock type
                    if request_data.asset_type == 'stock':
                        # Remove .VN suffix for Vietnamese stocks
                        clean_symbol = symbol.replace('.VN', '')
                        search_query = f"tin tức cổ phiếu {clean_symbol} OR công ty {clean_symbol} OR mã {clean_symbol}"
                    elif request_data.asset_type == 'crypto':
                        search_query = f"Important news for crypto currencies ticket {symbol}"

                    google_news = fetch_google_news(
                        search_query,
                        datetime.now().strftime('%Y-%m-%d'),
                        request_data.look_back_days
                    )
                    
                    if google_news:
                        # Parse Google News format
                        google_articles = parse_google_news_format(google_news, 'Google News')
                        aggregated_news.extend(google_articles[:request_data.max_results//2])
                        news_stats['sources_used'].append('google')
                        
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Error fetching Google News: {e}")
                    # Continue without Google News rather than failing completely
            
            # Remove duplicates based on title similarity
            if aggregated_news:
                aggregated_news = remove_duplicate_news(aggregated_news)
            
            # Add sentiment analysis
            if aggregated_news:
                aggregated_news = enhance_news_with_sentiment(aggregated_news)
            
            # Sort by relevance score and date
            if aggregated_news:
                aggregated_news.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            # Limit results
            aggregated_news = aggregated_news[:request_data.max_results]
            
            # Update statistics
            news_stats['total_articles'] = len(aggregated_news)
            news_stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            
            # Ensure we return something even if no news found
            if not aggregated_news:
                aggregated_news = []
            
            # Create response - Fix format to match frontend expectations
            return {
                'status': 'success',
                'data': aggregated_news,
                'symbol': symbol,
                'metadata': {
                    'symbol_type': 'vietnamese',
                    'search_parameters': {
                        'symbol': symbol,
                        'pages': request_data.pages,
                        'look_back_days': request_data.look_back_days,
                        'news_sources': request_data.news_sources,
                        'max_results': request_data.max_results
                    },
                    'statistics': news_stats
                },
                'authenticated': current_user is not None
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f">>> Lỗi trong /api/news: {e}")
            logger.error(f">>> Error details: {type(e).__name__}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail={
                    'status': 'error',
                    'message': f"Lỗi xử lý tin tức: {str(e)}",
                    'error_type': type(e).__name__,
                    'timestamp': datetime.now().isoformat()
                }
            )

@app.post("/api/send_alert")
async def send_alert_api(
    request_data: AlertRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user)
):
    """Gửi cảnh báo qua email"""
    try:
        send_alert(request_data.subject, request_data.signals, request_data.email)
        
        return {
            'success': True,
            'message': 'Cảnh báo đã được gửi thành công',
            'email': request_data.email,
            'sent_at': datetime.now().isoformat(),
            'authenticated': current_user is not None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.post("/api/optimize_portfolio")
@check_balance_and_track("portfolio_optimization")
async def optimize_portfolio_api(
    request_data: PortfolioOptimizationRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Tối ưu hóa danh mục đầu tư"""
    try:
        # Set default dates if not provided
        start_date = request_data.start_date or (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        end_date = request_data.end_date or datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"Optimizing portfolio for symbols: {request_data.symbols}")
        
        # Optimize portfolio
        result = optimize_portfolio(request_data.symbols, request_data.asset_type, start_date, end_date, request_data.investment_amount)
        
        # Add metadata to result
        if result.get('success'):
            result['metadata'] = {
                'optimization_date': datetime.now().isoformat(),
                'date_range': {'start': start_date, 'end': end_date},
                'symbols_count': len(request_data.symbols),
                'authenticated': current_user is not None
            }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.post("/api/calculate_manual_portfolio")
@check_balance_and_track("calculate_portfolio")
async def calculate_manual_portfolio_api(
    request_data: ManualPortfolioRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Tính toán hiệu suất danh mục thủ công"""
    try:
        # Frontend already sends weights as decimals (0.3 for 30%)
        manual_weights = request_data.manual_weights
        
        # Validate weights sum to 1
        total_weight = sum(manual_weights.values())
        if not (0.99 <= total_weight <= 1.01):  # Allow small rounding errors
            raise HTTPException(
                status_code=400, 
                detail=f"Tổng tỷ trọng phải bằng 100% (hiện tại: {total_weight*100:.1f}%)"
            )
        
        # Calculate manual portfolio
        result = calculate_manual_portfolio(
            manual_weights, 
            request_data.asset_type,
            request_data.start_date, 
            request_data.end_date, 
            request_data.investment_amount
        )
        
        # Add metadata to result
        if result.get('success'):
            result['metadata'] = {
                'calculation_date': datetime.now().isoformat(),
                'date_range': {'start': request_data.start_date, 'end': request_data.end_date},
                'original_weights': request_data.manual_weights,
                'authenticated': current_user is not None
            }
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")
    
@app.post("/api/technical-analysis/stream")
@check_balance_and_track_streaming("technical_analysis")
async def get_technical_analysis_stream_api(
    request_data: InsightsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Phân tích kỹ thuật với streaming response (Server-Sent Events) với Redis cache"""
    
    # Set default dates if not provided
    start_date = request_data.start_date or (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    end_date = request_data.end_date or datetime.now().strftime('%Y-%m-%d')
    
    async def generate_analysis():
        try:
            # Initialize metadata at the start            
            metadata = {
                'ticker': request_data.ticker,
                'generated_at': datetime.now().isoformat(),
                'date_range': {'start': start_date, 'end': end_date},
                'authenticated': current_user is not None,
                'analysis_type': 'technical_analysis'
            }
            
            # Send metadata first
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"
            
            # Create cache key for technical analysis
            cache_key = f"technical_analysis:{request_data.ticker.upper()}:{start_date}:{end_date}"
            
            try:
                # Try to get cached data from Redis
                redis_manager = get_redis_manager()
                cached_analysis = await redis_manager.get_json(cache_key)
                
                if cached_analysis:
                    # Send cached data with streaming format
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải dữ liệu từ cache...', 'progress': 10})}\n\n"
                    
                    content = cached_analysis.get('content', '')
                    if content:
                        yield f"data: {json.dumps({'type': 'section_start', 'section': 'technical_analysis', 'title': 'Phân Tích Kỹ Thuật'})}\n\n"
                        
                        # Stream content in chunks
                        words = content.split()
                        chunk_size = 20
                        for i in range(0, len(words), chunk_size):
                            chunk_text = ' '.join(words[i:i+chunk_size])
                            yield f"data: {json.dumps({'type': 'content', 'section': 'technical_analysis', 'text': chunk_text})}\n\n"
                            await asyncio.sleep(0.1)
                        
                        yield f"data: {json.dumps({'type': 'section_end', 'section': 'technical_analysis'})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích kỹ thuật hoàn tất từ cache!', 'progress': 100})}\n\n"
                    return
                    
            except Exception as cache_err:
                logger.warning(f"Cache error for technical analysis: {cache_err}")
                yield f"data: {json.dumps({'type': 'status', 'message': 'Cache không khả dụng, đang phân tích mới...', 'progress': 5})}\n\n"
            
            # No cache found, generate new analysis
            # Store content for caching
            analysis_content = ''
            
            # Generate streaming analysis and collect content for cache
            async for chunk in get_technical_analysis_streaming(
                ticker=request_data.ticker,
                asset_type=request_data.asset_type,
                start_date=start_date,
                end_date=end_date
            ):
                yield chunk
                
                # Parse chunk to collect content for caching
                try:
                    if chunk.startswith("data: "):
                        chunk_data = json.loads(chunk[6:].strip())
                        
                        if chunk_data.get('type') == 'content':
                            analysis_content += chunk_data.get('text', '') + ' '
                except:
                    pass
                
                # Add small delay to make streaming more visible
                await asyncio.sleep(0.05)
            
            # Cache the results for 6 hours
            try:
                redis_manager = get_redis_manager()
                await redis_manager.set_json(cache_key, {'content': analysis_content}, expire=21600)  # 6 hours
                logger.info(f"Cached technical analysis for {request_data.ticker}")
            except Exception as cache_err:
                logger.warning(f"Failed to cache technical analysis: {cache_err}")
            
            # Save to insights history if user is authenticated
            if current_user and analysis_content:
                try:
                    await insights_history_manager.save_insight(
                        user_id=current_user.id,
                        insight_data=InsightHistoryCreate(
                            ticker=request_data.ticker.upper(),
                            asset_type=request_data.asset_type,
                            analysis_type='technical_analysis',
                            content=analysis_content,
                            metadata={
                                'date_range': {'start': start_date, 'end': end_date},
                                'generated_at': datetime.now().isoformat()
                            }
                        )
                    )
                    logger.info(f"Saved technical analysis to history for user {current_user.id}")
                except Exception as save_err:
                    logger.error(f"Failed to save technical analysis to history: {save_err}")
                
        except Exception:
            yield f"data: {{\"type\": \"error\", \"message\": \"Server xử lý lỗi. Vui lòng thử lại.\"}}\n\n"
    
    return StreamingResponse(
        generate_analysis(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.post("/api/news-analysis/stream")
@check_balance_and_track_streaming("news_analysis") 
async def get_news_analysis_stream_api(
    request_data: InsightsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Phân tích tin tức với streaming response (Server-Sent Events) với Redis cache"""
    
    async def generate_analysis():
        try:
            # Initialize metadata at the start
            metadata = {
                'ticker': request_data.ticker,
                'generated_at': datetime.now().isoformat(),
                'look_back_days': request_data.look_back_days,
                'authenticated': current_user is not None,
                'analysis_type': 'news_analysis'
            }
            
            # Send metadata first
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"
            
            # Create cache key for news analysis
            cache_key = f"news_analysis:{request_data.ticker.upper()}:{request_data.look_back_days}"
            
            try:
                # Try to get cached data from Redis
                redis_manager = get_redis_manager()
                cached_analysis = await redis_manager.get_json(cache_key)
                
                if cached_analysis:
                    # Send cached data with streaming format
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải dữ liệu từ cache...', 'progress': 10})}\n\n"
                    
                    content = cached_analysis.get('content', '')
                    if content:
                        yield f"data: {json.dumps({'type': 'section_start', 'section': 'news_analysis', 'title': 'Phân Tích Tin Tức'})}\n\n"
                        
                        # Stream content in chunks
                        words = content.split()
                        chunk_size = 20
                        for i in range(0, len(words), chunk_size):
                            chunk_text = ' '.join(words[i:i+chunk_size])
                            yield f"data: {json.dumps({'type': 'content', 'section': 'news_analysis', 'text': chunk_text})}\n\n"
                            
                            await asyncio.sleep(0.1)
                        
                        yield f"data: {json.dumps({'type': 'section_end', 'section': 'news_analysis'})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích tin tức hoàn tất từ cache!', 'progress': 100})}\n\n"
                    return
                    
            except Exception as cache_err:
                logger.warning(f"Cache error for news analysis: {cache_err}")
                yield f"data: {json.dumps({'type': 'status', 'message': 'Cache không khả dụng, đang phân tích mới...', 'progress': 5})}\n\n"
            
            # No cache found, generate new analysis
            # Store content for caching
            analysis_content = ''
            
            # Generate streaming analysis and collect content for cache
            async for chunk in get_news_analysis_streaming(
                ticker=request_data.ticker,
                asset_type=request_data.asset_type,
                look_back_days=request_data.look_back_days
            ):
                yield chunk
                
                # Parse chunk to collect content for caching
                try:
                    if chunk.startswith("data: "):
                        chunk_data = json.loads(chunk[6:].strip())
                        
                        if chunk_data.get('type') == 'content':
                            analysis_content += chunk_data.get('text', '') + ' '
                except:
                    pass
                
                # Add small delay to make streaming more visible
                
                await asyncio.sleep(0.05)
            
            # Cache the results for 2 hours (news changes more frequently)
            try:
                redis_manager = get_redis_manager()
                await redis_manager.set_json(cache_key, {'content': analysis_content}, expire=7200)  # 2 hours
                logger.info(f"Cached news analysis for {request_data.ticker}")
            except Exception as cache_err:
                logger.warning(f"Failed to cache news analysis: {cache_err}")
                
            # Save to insights history if user is authenticated
            if current_user and analysis_content:
                try:
                    await insights_history_manager.save_insight(
                        user_id=current_user.id,
                        insight_data=InsightHistoryCreate(
                            ticker=request_data.ticker.upper(),
                            asset_type=request_data.asset_type,
                            analysis_type='news_analysis',
                            content=analysis_content,
                            metadata={
                                'look_back_days': request_data.look_back_days,
                                'generated_at': datetime.now().isoformat()
                            }
                        )
                    )
                    logger.info(f"Saved news analysis to history for user {current_user.id}")
                except Exception as save_err:
                    logger.error(f"Failed to save news analysis to history: {save_err}")
                
        except Exception:
            yield f"data: {{\"type\": \"error\", \"message\": \"Server xử lý lỗi. Vui lòng thử lại.\"}}\n\n"
    
    return StreamingResponse(
        generate_analysis(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.post("/api/proprietary-trading-analysis/stream")
@check_balance_and_track_streaming("proprietary_trading_analysis")
async def get_proprietary_trading_analysis_stream_api(
    request_data: InsightsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Phân tích giao dịch tự doanh với streaming response (Server-Sent Events) với Redis cache"""
    
    async def generate_analysis():
        try:
            # Initialize metadata at the start
            metadata = {
                'ticker': request_data.ticker,
                'generated_at': datetime.now().isoformat(),
                'authenticated': current_user is not None,
                'analysis_type': 'proprietary_trading_analysis'
            }
            
            # Send metadata first
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"
            
            # Create cache key for proprietary trading analysis
            cache_key = f"proprietary_trading:{request_data.ticker.upper()}"
            
            try:
                # Try to get cached data from Redis
                redis_manager = get_redis_manager()
                cached_analysis = await redis_manager.get_json(cache_key)
                
                if cached_analysis:
                    # Send cached data with streaming format
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải dữ liệu từ cache...', 'progress': 10})}\n\n"
                    
                    content = cached_analysis.get('content', '')
                    if content:
                        yield f"data: {json.dumps({'type': 'section_start', 'section': 'proprietary_trading_analysis', 'title': 'Phân Tích Giao Dịch Tự Doanh'})}\n\n"
                        
                        # Stream content in chunks
                        words = content.split()
                        chunk_size = 20
                        for i in range(0, len(words), chunk_size):
                            chunk_text = ' '.join(words[i:i+chunk_size])
                            yield f"data: {json.dumps({'type': 'content', 'section': 'proprietary_trading_analysis', 'text': chunk_text})}\n\n"
                            
                            await asyncio.sleep(0.1)
                        
                        yield f"data: {json.dumps({'type': 'section_end', 'section': 'proprietary_trading_analysis'})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích giao dịch tự doanh hoàn tất từ cache!', 'progress': 100})}\n\n"
                    return
                    
            except Exception as cache_err:
                logger.warning(f"Cache error for proprietary trading analysis: {cache_err}")
                yield f"data: {json.dumps({'type': 'status', 'message': 'Cache không khả dụng, đang phân tích mới...', 'progress': 5})}\n\n"
            
            # No cache found, generate new analysis
            # Store content for caching
            analysis_content = ''
            
            # Generate streaming analysis and collect content for cache
            async for chunk in get_proprietary_trading_analysis_streaming(
                ticker=request_data.ticker
            ):
                yield chunk
                
                # Parse chunk to collect content for caching
                try:
                    if chunk.startswith("data: "):
                        chunk_data = json.loads(chunk[6:].strip())
                        
                        if chunk_data.get('type') == 'content':
                            analysis_content += chunk_data.get('text', '') + ' '
                except:
                    pass
                
                # Add small delay to make streaming more visible
                
                await asyncio.sleep(0.05)
            
            # Cache the results for 4 hours
            try:
                redis_manager = get_redis_manager()
                await redis_manager.set_json(cache_key, {'content': analysis_content}, expire=14400)  # 4 hours
                logger.info(f"Cached proprietary trading analysis for {request_data.ticker}")
            except Exception as cache_err:
                logger.warning(f"Failed to cache proprietary trading analysis: {cache_err}")
            
            # Save to insights history if user is authenticated
            if current_user and analysis_content:
                try:
                    await insights_history_manager.save_insight(
                        user_id=current_user.id,
                        insight_data=InsightHistoryCreate(
                            ticker=request_data.ticker.upper(),
                            asset_type='stock',
                            analysis_type='proprietary_trading_analysis',
                            content=analysis_content,
                            metadata={
                                'generated_at': datetime.now().isoformat()
                            }
                        )
                    )
                    logger.info(f"Saved proprietary trading analysis to history for user {current_user.id}")
                except Exception as save_err:
                    logger.error(f"Failed to save proprietary trading analysis to history: {save_err}")
                
        except Exception:
            yield f"data: {{\"type\": \"error\", \"message\": \"Server xử lý lỗi. Vui lòng thử lại.\"}}\n\n"
    
    return StreamingResponse(
        generate_analysis(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.post("/api/foreign-trading-analysis/stream")
@check_balance_and_track_streaming("foreign_trading_analysis")
async def get_foreign_trading_analysis_stream_api(
    request_data: InsightsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Phân tích giao dịch khối ngoại với streaming response (Server-Sent Events) với Redis cache"""
    
    async def generate_analysis():
        try:
            # Initialize metadata at the start
            metadata = {
                'ticker': request_data.ticker,
                'generated_at': datetime.now().isoformat(),
                'authenticated': current_user is not None,
                'analysis_type': 'foreign_trading_analysis'
            }
            
            # Send metadata first
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"
            
            # Create cache key for foreign trading analysis
            cache_key = f"foreign_trading:{request_data.ticker.upper()}"
            
            try:
                # Try to get cached data from Redis
                redis_manager = get_redis_manager()
                cached_analysis = await redis_manager.get_json(cache_key)
                
                if cached_analysis:
                    # Send cached data with streaming format
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải dữ liệu từ cache...', 'progress': 10})}\n\n"
                    
                    content = cached_analysis.get('content', '')
                    if content:
                        yield f"data: {json.dumps({'type': 'section_start', 'section': 'foreign_trading_analysis', 'title': 'Phân Tích Giao Dịch Khối Ngoại'})}\n\n"
                        
                        # Stream content in chunks
                        words = content.split()
                        chunk_size = 20
                        for i in range(0, len(words), chunk_size):
                            chunk_text = ' '.join(words[i:i+chunk_size])
                            yield f"data: {json.dumps({'type': 'content', 'section': 'foreign_trading_analysis', 'text': chunk_text})}\n\n"
                            
                            await asyncio.sleep(0.1)
                        
                        yield f"data: {json.dumps({'type': 'section_end', 'section': 'foreign_trading_analysis'})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích giao dịch khối ngoại hoàn tất từ cache!', 'progress': 100})}\n\n"
                    return
                    
            except Exception as cache_err:
                logger.warning(f"Cache error for foreign trading analysis: {cache_err}")
                yield f"data: {json.dumps({'type': 'status', 'message': 'Cache không khả dụng, đang phân tích mới...', 'progress': 5})}\n\n"
            
            # No cache found, generate new analysis
            # Store content for caching
            analysis_content = ''
            
            # Generate streaming analysis and collect content for cache
            async for chunk in get_foreign_trading_analysis_streaming(
                ticker=request_data.ticker
            ):
                yield chunk
                
                # Parse chunk to collect content for caching
                try:
                    if chunk.startswith("data: "):
                        chunk_data = json.loads(chunk[6:].strip())
                        
                        if chunk_data.get('type') == 'content':
                            analysis_content += chunk_data.get('text', '') + ' '
                except:
                    pass
                
                # Add small delay to make streaming more visible
                
                await asyncio.sleep(0.05)
            
            # Cache the results for 4 hours
            try:
                redis_manager = get_redis_manager()
                await redis_manager.set_json(cache_key, {'content': analysis_content}, expire=14400)  # 4 hours
                logger.info(f"Cached foreign trading analysis for {request_data.ticker}")
            except Exception as cache_err:
                logger.warning(f"Failed to cache foreign trading analysis: {cache_err}")
            
            # Save to insights history if user is authenticated
            if current_user and analysis_content:
                try:
                    await insights_history_manager.save_insight(
                        user_id=current_user.id,
                        insight_data=InsightHistoryCreate(
                            ticker=request_data.ticker.upper(),
                            asset_type='stock',
                            analysis_type='foreign_trading_analysis',
                            content=analysis_content,
                            metadata={
                                'generated_at': datetime.now().isoformat()
                            }
                        )
                    )
                    logger.info(f"Saved foreign trading analysis to history for user {current_user.id}")
                except Exception as save_err:
                    logger.error(f"Failed to save foreign trading analysis to history: {save_err}")
                
        except Exception:
            yield f"data: {{\"type\": \"error\", \"message\": \"Server xử lý lỗi. Vui lòng thử lại.\"}}\n\n"
    
    return StreamingResponse(
        generate_analysis(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.post("/api/shareholder-trading-analysis/stream")
@check_balance_and_track_streaming("shareholder_trading_analysis")
async def get_shareholder_trading_analysis_stream_api(
    request_data: InsightsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Phân tích giao dịch cổ đông nội bộ với streaming response (Server-Sent Events) với Redis cache"""
    
    async def generate_analysis():
        try:
            # Initialize metadata at the start
            metadata = {
                'ticker': request_data.ticker,
                'generated_at': datetime.now().isoformat(),
                'authenticated': current_user is not None,
                'analysis_type': 'shareholder_trading_analysis'
            }
            
            # Send metadata first
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"
            
            # Create cache key for shareholder trading analysis
            cache_key = f"shareholder_trading:{request_data.ticker.upper()}"
            
            try:
                # Try to get cached data from Redis
                redis_manager = get_redis_manager()
                cached_analysis = await redis_manager.get_json(cache_key)
                
                if cached_analysis:
                    # Send cached data with streaming format
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải dữ liệu từ cache...', 'progress': 10})}\n\n"
                    
                    content = cached_analysis.get('content', '')
                    if content:
                        yield f"data: {json.dumps({'type': 'section_start', 'section': 'shareholder_trading_analysis', 'title': 'Phân Tích Giao Dịch Cổ Đông Nội Bộ'})}\n\n"
                        
                        # Stream content in chunks
                        words = content.split()
                        chunk_size = 20
                        for i in range(0, len(words), chunk_size):
                            chunk_text = ' '.join(words[i:i+chunk_size])
                            yield f"data: {json.dumps({'type': 'content', 'section': 'shareholder_trading_analysis', 'text': chunk_text})}\n\n"
                            
                            await asyncio.sleep(0.1)
                        
                        yield f"data: {json.dumps({'type': 'section_end', 'section': 'shareholder_trading_analysis'})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích giao dịch cổ đông hoàn tất từ cache!', 'progress': 100})}\n\n"
                    return
                    
            except Exception as cache_err:
                logger.warning(f"Cache error for shareholder trading analysis: {cache_err}")
                yield f"data: {json.dumps({'type': 'status', 'message': 'Cache không khả dụng, đang phân tích mới...', 'progress': 5})}\n\n"
            
            # No cache found, generate new analysis
            # Store content for caching
            analysis_content = ''
            
            # Generate streaming analysis and collect content for cache
            async for chunk in get_shareholder_trading_analysis_streaming(
                ticker=request_data.ticker
            ):
                yield chunk
                
                # Parse chunk to collect content for caching
                try:
                    if chunk.startswith("data: "):
                        chunk_data = json.loads(chunk[6:].strip())
                        
                        if chunk_data.get('type') == 'content':
                            analysis_content += chunk_data.get('text', '') + ' '
                except:
                    pass
                
                # Add small delay to make streaming more visible
                
                await asyncio.sleep(0.05)
            
            # Cache the results for 8 hours
            try:
                redis_manager = get_redis_manager()
                await redis_manager.set_json(cache_key, {'content': analysis_content}, expire=28800)  # 8 hours
                logger.info(f"Cached shareholder trading analysis for {request_data.ticker}")
            except Exception as cache_err:
                logger.warning(f"Failed to cache shareholder trading analysis: {cache_err}")
            
            # Save to insights history if user is authenticated
            if current_user and analysis_content:
                try:
                    await insights_history_manager.save_insight(
                        user_id=current_user.id,
                        insight_data=InsightHistoryCreate(
                            ticker=request_data.ticker.upper(),
                            asset_type='stock',
                            analysis_type='shareholder_trading_analysis',
                            content=analysis_content,
                            metadata={
                                'generated_at': datetime.now().isoformat()
                            }
                        )
                    )
                    logger.info(f"Saved shareholder trading analysis to history for user {current_user.id}")
                except Exception as save_err:
                    logger.error(f"Failed to save shareholder trading analysis to history: {save_err}")
                
        except Exception:
            yield f"data: {{\"type\": \"error\", \"message\": \"Server xử lý lỗi. Vui lòng thử lại.\"}}\n\n"
    
    return StreamingResponse(
        generate_analysis(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.post("/api/intraday_match_analysis")
@check_balance_and_track_streaming("intraday_match_analysis")
async def get_intraday_match_analysis_api(
    ticker: str = Query(..., description="Mã cổ phiếu"),
    date: str = Query(..., description="Ngày phân tích (YYYY-MM-DD hoặc YYYYMMDD)"),
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Phân tích khớp lệnh trong phiên với streaming response với Redis cache"""
    
    try:
        async def generate_analysis():
            try:
                # Send metadata first
                metadata = {
                    'ticker': ticker.upper(),
                    'date': date,
                    'generated_at': datetime.now().isoformat(),
                    'authenticated': current_user is not None
                }
                yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"
                
                # Create cache key for intraday analysis
                cache_key = f"intraday_analysis:{ticker.upper()}:{date}"
                
                try:
                    # Try to get cached data from Redis
                    redis_manager = get_redis_manager()
                    cached_analysis = await redis_manager.get_json(cache_key)
                    
                    if cached_analysis:
                        # Send cached data with streaming format
                        yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tải dữ liệu từ cache...', 'progress': 10})}\n\n"
                        
                        content = cached_analysis.get('content', '')
                        if content:
                            yield f"data: {json.dumps({'type': 'section_start', 'section': 'intraday_analysis', 'title': 'Phân Tích Khớp Lệnh Trong Phiên'})}\n\n"
                            
                            # Stream content in chunks
                            words = content.split()
                            chunk_size = 20
                            for i in range(0, len(words), chunk_size):
                                chunk_text = ' '.join(words[i:i+chunk_size])
                                yield f"data: {json.dumps({'type': 'content', 'section': 'intraday_analysis', 'text': chunk_text})}\n\n"
                                await asyncio.sleep(0.1)
                            
                            yield f"data: {json.dumps({'type': 'section_end', 'section': 'intraday_analysis'})}\n\n"
                        
                        yield f"data: {json.dumps({'type': 'complete', 'message': 'Phân tích khớp lệnh hoàn tất từ cache!', 'progress': 100})}\n\n"
                        return
                        
                except Exception as cache_err:
                    logger.warning(f"Cache error for intraday analysis: {cache_err}")
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Cache không khả dụng, đang phân tích mới...', 'progress': 5})}\n\n"
                
                # No cache found, generate new analysis
                analysis_content = ''
                
                # Generate streaming analysis and collect content for cache
                async for chunk in get_intraday_match_analysis_streaming(symbol=ticker, date=date):
                    yield chunk
                    
                    # Parse chunk to collect content for caching
                    try:
                        if chunk.startswith("data: "):
                            chunk_data = json.loads(chunk[6:].strip())
                            
                            if chunk_data.get('type') == 'content':
                                analysis_content += chunk_data.get('text', '') + ' '
                    except:
                        pass
                    
                    # Add small delay to make streaming more visible
                    await asyncio.sleep(0.05)
                
                # Cache the results for 12 hours (intraday data changes less frequently)
                try:
                    redis_manager = get_redis_manager()
                    await redis_manager.set_json(cache_key, {'content': analysis_content}, expire=43200)  # 12 hours
                    logger.info(f"Cached intraday analysis for {ticker} on {date}")
                except Exception as cache_err:
                    logger.warning(f"Failed to cache intraday analysis: {cache_err}")
                
                # Save to insights history if user is authenticated
                if current_user and analysis_content:
                    try:
                        await insights_history_manager.save_insight(
                            user_id=current_user.id,
                            insight_data=InsightHistoryCreate(
                                ticker=ticker.upper(),
                                asset_type='stock',
                                analysis_type='intraday_match_analysis',
                                content=analysis_content,
                                metadata={
                                    'date': date,
                                    'generated_at': datetime.now().isoformat()
                                }
                            )
                        )
                        logger.info(f"Saved intraday match analysis to history for user {current_user.id}")
                    except Exception as save_err:
                        logger.error(f"Failed to save intraday match analysis to history: {save_err}")
                    
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi phân tích: {e}'})}\n\n"
        
        return StreamingResponse(
            generate_analysis(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in intraday match analysis API: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích khớp lệnh: {str(e)}")

# ================================
# HEALTH CHECK AND INFO ROUTES
# ================================

@app.get("/health")
async def health_check():
    """Kiểm tra tình trạng ứng dụng"""
    try:
        db_status = test_supabase_connection()
        return {
            "status": "healthy" if db_status else "degraded",
            "database": "connected" if db_status else "disconnected",
            "timestamp": datetime.now().isoformat(),
            "version": "3.0.0",
            "framework": "FastAPI + Supabase"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "version": "3.0.0"
        }

@app.get("/api")
async def api_info():
    """Thông tin API"""
    return {
        "name": "FRM-AI Financial Risk Management API",
        "version": "3.0.0",
        "framework": "FastAPI + Supabase",
        "description": "Hệ thống quản lý rủi ro tài chính với AI và Blockchain",
        "features": [
            "User Authentication & Authorization",
            "FRM Coin Wallet System",
            "Service Packages & Subscriptions",
            "Service Usage Tracking",
            "Real-time Notifications",
            "Advanced Financial Analysis",
            "AI-powered Insights",
            "Portfolio Optimization",
            "Technical & Fundamental Analysis",
            "News Analysis with Sentiment",
            "Admin Dashboard & Analytics"
        ],
        "endpoints": {
            "auth": "Authentication & User Management",
            "wallet": "FRM Coin Wallet Operations",
            "packages": "Service Packages & Subscriptions",
            "notifications": "Real-time Notifications",
            "service-usage": "Usage Tracking & Analytics",
            "admin": "Administrative Functions",
            # "stock_analysis": "Stock Analysis & Forecasting",
            "technical_analysis": "Technical Analysis & Signals",
            "portfolio": "Portfolio Optimization",
            "news": "News Analysis with AI",
            "insights": "AI-powered Market Insights"
        },
        "docs": "/docs",
        "redoc": "/redoc",
        "database": "Supabase PostgreSQL",
        "authentication": "JWT Bearer Token"
    }

# ================================
# ERROR HANDLERS
# ================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )

# ================================
# SYSTEM MONITORING ENDPOINTS
# ================================

@app.get("/api/system/health")
async def health_check():
    """System health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0",
        "environment": "production"
    }

@app.get("/api/system/metrics")
async def get_system_metrics():
    """Get system performance metrics"""
    stats = performance_monitor.get_stats()
    
    return {
        "success": True,
        "metrics": stats,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/system/status")
async def get_system_status():
    """Get comprehensive system status"""
    try:
        # Test database connection
        supabase = get_supabase_client()
        db_test = supabase.table("users").select("id").limit(1).execute()
        db_status = "connected" if db_test else "disconnected"
    except Exception:
        db_status = "error"
    
    # Test Redis connection
    try:
        redis_manager = get_redis_manager()
        redis_status = "connected" if redis_manager.is_connected() else "disconnected"
    except Exception:
        redis_status = "error"
    
    # Get cache status
    try:
        cache_manager = get_cache_manager()
        cache_status = cache_manager.get_cache_status()
    except Exception as e:
        cache_status = {"error": str(e)}
    
    return {
        "success": True,
        "status": {
            "database": db_status,
            "redis": redis_status,
            "cache": cache_status,
            "performance": performance_monitor.get_stats(),
            "timestamp": datetime.now().isoformat()
        }
    }

# ================================
# CACHE MANAGEMENT ROUTES
# ================================

@app.get("/api/cache/status")
async def get_cache_status():
    """Get cache system status and statistics"""
    try:
        cache_manager = get_cache_manager()
        return {
            "success": True,
            "cache_status": cache_manager.get_cache_status()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/cache/refresh")
async def trigger_cache_refresh(
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Manually trigger a full cache refresh (Admin only)"""
    try:
        cache_manager = get_cache_manager()
        
        # Run cache refresh in background
        import threading
        thread = threading.Thread(target=cache_manager.daily_full_fetch)
        thread.start()
        
        return {
            "success": True,
            "message": "Cache refresh triggered successfully",
            "note": "Refresh is running in background"
        }
    except Exception as e:
        logger.error(f"Error triggering cache refresh: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger cache refresh: {str(e)}")

@app.delete("/api/cache/clear")
async def clear_cache(
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Clear all cached data (Admin only)"""
    try:
        redis_manager = get_redis_manager()
        redis_manager.clear_cache()
        
        return {
            "success": True,
            "message": "Cache cleared successfully"
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@app.get("/api/cache/symbols")
async def get_cached_symbols():
    """Get list of cached symbols"""
    try:
        redis_manager = get_redis_manager()
        symbols = redis_manager.get_cached_symbols()
        
        return {
            "success": True,
            "cached_symbols": symbols,
            "count": len(symbols)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/cache/symbol/{symbol}")
async def check_symbol_cache(symbol: str):
    """Check if a specific symbol is cached"""
    try:
        redis_manager = get_redis_manager()
        is_cached = redis_manager.is_symbol_cached(symbol)
        cached_data = redis_manager.get_stock_data(symbol) if is_cached else None
        
        return {
            "success": True,
            "symbol": symbol.upper(),
            "is_cached": is_cached,
            "cache_info": {
                "last_updated": cached_data.get("last_updated") if cached_data else None,
                "data_points": cached_data.get("data_points") if cached_data else 0,
                "asset_type": cached_data.get("asset_type") if cached_data else None
            } if cached_data else None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ==================== CAFEF FREE APIs ====================

@app.post("/api/cafef/shareholder-data")
async def api_get_shareholder_data(request: ShareholderDataRequest):
    """Lấy dữ liệu giao dịch cổ đông (Free API - không cần check balance)"""
    try:
        data = get_shareholder_data(
            symbol=request.symbol.upper(),
            start_date=request.start_date,
            end_date=request.end_date,
            page_index=request.page_index,
            page_size=request.page_size
        )
        
        return {
            "success": True,
            "symbol": request.symbol.upper(),
            "data": data,
            "page_index": request.page_index,
            "page_size": request.page_size
        }
    except Exception as e:
        logger.error(f"Error getting shareholder data: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy dữ liệu giao dịch cổ đông: {str(e)}")

@app.post("/api/cafef/price-history")
async def api_get_price_history(request: PriceHistoryRequest):
    """Lấy lịch sử giá cổ phiếu (Free API - không cần check balance)"""
    try:
        data = get_price_history(
            symbol=request.symbol.upper(),
            start_date=request.start_date,
            end_date=request.end_date,
            page_index=request.page_index,
            page_size=request.page_size
        )
        
        return {
            "success": True,
            "symbol": request.symbol.upper(),
            "data": data,
            "page_index": request.page_index,
            "page_size": request.page_size
        }
    except Exception as e:
        logger.error(f"Error getting price history: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy lịch sử giá: {str(e)}")

@app.post("/api/cafef/foreign-trading")
async def api_get_foreign_trading_data(request: ForeignTradingRequest):
    """Lấy dữ liệu giao dịch khối ngoại (Free API - không cần check balance)"""
    try:
        data = get_foreign_trading_data(
            symbol=request.symbol.upper(),
            start_date=request.start_date,
            end_date=request.end_date,
            page_index=request.page_index,
            page_size=request.page_size
        )
        
        return {
            "success": True,
            "symbol": request.symbol.upper(),
            "data": data,
            "page_index": request.page_index,
            "page_size": request.page_size
        }
    except Exception as e:
        logger.error(f"Error getting foreign trading data: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy dữ liệu giao dịch khối ngoại: {str(e)}")

@app.post("/api/cafef/proprietary-trading")
async def api_get_proprietary_trading_data(request: ProprietaryTradingRequest):
    """Lấy dữ liệu giao dịch tự doanh (Free API - không cần check balance)"""
    try:
        data = get_proprietary_trading_data(
            symbol=request.symbol.upper(),
            start_date=request.start_date,
            end_date=request.end_date,
            page_index=request.page_index,
            page_size=request.page_size
        )
        
        return {
            "success": True,
            "symbol": request.symbol.upper(),
            "data": data,
            "page_index": request.page_index,
            "page_size": request.page_size
        }
    except Exception as e:
        logger.error(f"Error getting proprietary trading data: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy dữ liệu giao dịch tự doanh: {str(e)}")

@app.post("/api/cafef/match-price")
async def api_get_match_price(request: MatchPriceRequest):
    """Lấy giá khớp lệnh theo ngày (Free API - không cần check balance)"""
    try:
        data = get_match_price(
            symbol=request.symbol.upper(),
            date=request.date
        )
        
        return {
            "success": True,
            "symbol": request.symbol.upper(),
            "date": request.date,
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting match price: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy giá khớp lệnh: {str(e)}")

@app.get("/api/cafef/realtime-price/{symbol}")
async def api_get_realtime_price(symbol: str):
    """Lấy giá realtime (Free API - không cần check balance)"""
    try:
        data = get_realtime_price(symbol.upper())
        
        return {
            "success": True,
            "symbol": symbol.upper(),
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting realtime price: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy giá realtime: {str(e)}")

@app.get("/api/cafef/company-info/{symbol}")
async def api_get_company_info(symbol: str):
    """Lấy thông tin công ty (Free API - trả về file .aspx)"""
    try:
        data = get_company_info(symbol.upper())
        
        # Trả về raw content cho file .aspx
        return Response(
            content=data,
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename={symbol.upper()}_company_info.aspx"
            }
        )
    except Exception as e:
        logger.error(f"Error getting company info: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy thông tin công ty: {str(e)}")

@app.get("/api/cafef/leadership/{symbol}")
async def api_get_leadership(symbol: str):
    """Lấy danh sách ban lãnh đạo (Free API - trả về file .aspx)"""
    try:
        data = get_leadership(symbol.upper())
        
        # Trả về raw content cho file .aspx
        return Response(
            content=data,
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename={symbol.upper()}_leadership.aspx"
            }
        )
    except Exception as e:
        logger.error(f"Error getting leadership data: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy danh sách ban lãnh đạo: {str(e)}")

@app.get("/api/cafef/subsidiaries/{symbol}")
async def api_get_subsidiaries(symbol: str):
    """Lấy danh sách công ty con (Free API - trả về file .aspx)"""
    try:
        data = get_subsidiaries(symbol.upper())
        
        # Trả về raw content cho file .aspx
        return Response(
            content=data,
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename={symbol.upper()}_subsidiaries.aspx"
            }
        )
    except Exception as e:
        logger.error(f"Error getting subsidiaries data: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy danh sách công ty con: {str(e)}")

@app.get("/api/cafef/financial-reports/{symbol}")
async def api_get_financial_reports(symbol: str):
    """Lấy báo cáo tài chính (Free API - trả về file .aspx)"""
    try:
        data = get_financial_reports(symbol.upper())
        
        # Trả về raw content cho file .aspx
        return Response(
            content=data,
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename={symbol.upper()}_financial_reports.aspx"
            }
        )
    except Exception as e:
        logger.error(f"Error getting financial reports: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy báo cáo tài chính: {str(e)}")

@app.post("/api/cafef/company-profile")
async def api_get_company_profile(request: CompanyProfileRequest):
    """Lấy hồ sơ công ty (Free API - trả về file .aspx)"""
    try:
        data = get_company_profile(
            symbol=request.symbol.upper(),
            type_id=request.type_id,
            page_index=request.page_index,
            page_size=request.page_size
        )
        
        # Trả về raw content cho file .aspx
        return Response(
            content=data,
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename={request.symbol.upper()}_company_profile.aspx"
            }
        )
    except Exception as e:
        logger.error(f"Error getting company profile: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy hồ sơ công ty: {str(e)}")

@app.get("/api/cafef/finance-data/{symbol}")
async def api_get_finance_data(symbol: str):
    """Lấy dữ liệu tài chính (Free API - không cần check balance)"""
    try:
        data = get_finance_data(symbol.upper())
        
        return {
            "success": True,
            "symbol": symbol.upper(),
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting finance data: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy dữ liệu tài chính: {str(e)}")

@app.get("/api/cafef/global-indices")
async def api_get_global_indices():
    """Lấy chỉ số thế giới (Free API - không cần check balance)"""
    try:
        data = get_global_indices()
        
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting global indices: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy chỉ số thế giới: {str(e)}")

if __name__ == '__main__':
    uvicorn.run(
        "app_fastapi:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        access_log=True,
        log_level="info"
    )