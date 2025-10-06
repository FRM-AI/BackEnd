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
import asyncio
import logging
import time

# Import custom modules
from chat_manager import ChatManager, ChatMessage, ConnectionManager
import re
from difflib import SequenceMatcher
import uvicorn
import logging

from pathlib import Path

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
from social_manager import (
    social_manager, UserProfile, UserProfileUpdate, UserProfileInfo, 
    FollowInfo, Post, PostCreate, PostUpdate, Comment, CommentCreate
)
from chat_manager import chat_manager, ChatMessage, Conversation

from data_loader import load_stock_data_vn, load_stock_data_yf
from feature_engineering import add_technical_indicators_vnquant, add_technical_indicators_yf
from technical_analysis import detect_signals
from fundamental_scoring_vn import score_stock, rank_stocks
from portfolio_optimization import optimize_portfolio, calculate_manual_portfolio
from alert import send_alert
from news_analysis import get_insights, get_insights_streaming
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
                    'source': news_source,
                    'link': news_link,
                    'date': news_date,
                    'relevance_score': calculate_relevance_score(title, '')
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

# Add GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add trusted host middleware for production security
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "*.vercel.app", "https://api.frmai.org", "*"]
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

# CORS Configuration - Fixed for proper localhost access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development
        "http://localhost:3001",  # Alternative Next.js port
        "http://localhost:8000",  # FastAPI server
        "http://127.0.0.1:3000",  # Alternative localhost format
        "http://127.0.0.1:8000",  # Alternative localhost format
        "http://127.0.0.1:8080",  # Python http.server for templates
        "http://localhost:8080",  # Python http.server for templates
        "http://0.0.0.0:8000",   # Explicit 0.0.0.0 binding
        "file://",               # For local file access
        "null",                  # For local file access
        "https://frm-ai-fe-0c4c7014ba75.herokuapp.com",   # Vercel deployments
        "https://www.frmai.org",
        "https://frm-ai-be-ae82305655d8.herokuapp.com", # Production domain
        # Add more domains as needed
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Authorization", 
        "Content-Type", 
        "Accept", 
        "Origin", 
        "User-Agent", 
        "X-Requested-With",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
        "Cache-Control",
        "Pragma"
    ],
    expose_headers=[
        "X-Total-Count",
        "X-Page-Count", 
        "X-Rate-Limit-Limit",
        "X-Rate-Limit-Remaining",
        "X-Rate-Limit-Reset"
    ]
)

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
        
        # Initialize chat manager
        global chat_manager
        chat_manager = ChatManager()
        logger.info("✅ Chat manager initialized")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")

# Initialize global variables
chat_manager: Optional[ChatManager] = None

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
# SOCIAL MEDIA ROUTES
# ================================

# ---- User Profile Management ----

@app.get("/api/users/{user_id}/profile", response_model=UserProfileInfo)
async def get_user_profile(
    user_id: str,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user)
):
    """Lấy thông tin hồ sơ người dùng"""
    current_user_id = current_user.id if current_user else None
    return await social_manager.get_user_profile(user_id, current_user_id)

@app.put("/api/users/{user_id}/profile", response_model=UserProfile)
async def update_user_profile(
    user_id: str,
    profile_data: UserProfileUpdate,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Cập nhật hồ sơ cá nhân"""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Không có quyền chỉnh sửa hồ sơ này")
    return await social_manager.update_user_profile(user_id, profile_data)

@app.get("/api/users/{user_id}/followers", response_model=List[FollowInfo])
async def get_user_followers(
    user_id: str,
    limit: int = 50,
    offset: int = 0
):
    """Lấy danh sách người theo dõi"""
    return await social_manager.get_followers(user_id, limit, offset)

@app.get("/api/users/{user_id}/following", response_model=List[FollowInfo])
async def get_user_following(
    user_id: str,
    limit: int = 50,
    offset: int = 0
):
    """Lấy danh sách người đang theo dõi"""
    return await social_manager.get_following(user_id, limit, offset)

@app.post("/api/users/{user_id}/follow")
async def follow_user(
    user_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Theo dõi người dùng khác"""
    return await social_manager.follow_user(current_user.id, user_id)

@app.delete("/api/users/{user_id}/unfollow")
async def unfollow_user(
    user_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Bỏ theo dõi người dùng khác"""
    return await social_manager.unfollow_user(current_user.id, user_id)

# ---- Post Management ----

@app.post("/api/posts", response_model=Post)
async def create_post(
    post_data: PostCreate,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Tạo bài viết (blog, phân tích)"""
    return await social_manager.create_post(current_user.id, post_data)

@app.get("/api/posts/{post_id}")
async def get_post_detail(
    post_id: str,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user)
):
    """Lấy chi tiết bài viết"""
    try:
        post = await social_manager.get_post(post_id, current_user.id if current_user else None)
        return post
    except Exception as e:
        logger.error(f"Error getting post detail: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi khi lấy chi tiết bài viết")

@app.get("/api/posts", response_model=List[Post])
async def get_posts(
    user_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user)
):
    """Lấy danh sách bài viết (có thể lọc theo người dùng, mã cổ phiếu, hoặc loại nội dung)"""
    current_user_id = current_user.id if current_user else None
    return await social_manager.get_posts(user_id, tags, limit, offset, current_user_id)

@app.get("/api/posts/{post_id}", response_model=Post)
async def get_post_detail(
    post_id: str,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user)
):
    """Lấy chi tiết bài viết"""
    current_user_id = current_user.id if current_user else None
    return await social_manager.get_post(post_id, current_user_id)

@app.put("/api/posts/{post_id}", response_model=Post)
async def update_post(
    post_id: str,
    update_data: PostUpdate,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Cập nhật bài viết"""
    return await social_manager.update_post(post_id, current_user.id, update_data)

@app.delete("/api/posts/{post_id}")
async def delete_post(
    post_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Xóa bài viết"""
    return await social_manager.delete_post(post_id, current_user.id)

# ---- Comment Management ----

@app.post("/api/posts/{post_id}/comments", response_model=Comment)
async def create_comment(
    post_id: str,
    comment_data: CommentCreate,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Bình luận dưới bài viết"""
    return await social_manager.create_comment(post_id, current_user.id, comment_data)

@app.get("/api/posts/{post_id}/comments", response_model=List[Comment])
async def get_post_comments(
    post_id: str,
    limit: int = 50,
    offset: int = 0
):
    """Lấy danh sách bình luận"""
    return await social_manager.get_comments(post_id, limit, offset)

@app.delete("/api/comments/{comment_id}")
async def delete_comment(
    comment_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Xóa bình luận"""
    return await social_manager.delete_comment(comment_id, current_user.id)

# ---- Like Management (Optional) ----

@app.post("/api/posts/{post_id}/like")
async def like_post(
    post_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Thích bài viết"""
    return await social_manager.like_post(post_id, current_user.id)

@app.delete("/api/posts/{post_id}/like")
async def unlike_post(
    post_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Bỏ thích bài viết"""
    return await social_manager.unlike_post(post_id, current_user.id)

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

# ---- Admin Social Management ----

@app.get("/api/admin/posts")
async def get_all_posts_admin(
    limit: int = 50,
    offset: int = 0,
    user_id: Optional[str] = None,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Lấy tất cả bài viết (admin)"""
    return await social_manager.get_posts(user_id, None, limit, offset, None)

@app.delete("/api/admin/posts/{post_id}")
async def delete_post_admin(
    post_id: str,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Xóa bài viết (admin)"""
    # Admin có thể xóa bất kỳ bài viết nào
    try:
        # Get post info first to get user_id for the delete function
        post = await social_manager.get_post(post_id, None)
        return await social_manager.delete_post(post_id, post.user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin delete post error: {e}")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi xóa bài viết")

@app.delete("/api/admin/comments/{comment_id}")
async def delete_comment_admin(
    comment_id: str,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Xóa bình luận (admin)"""
    # Admin có thể xóa bất kỳ bình luận nào
    try:
        # Get comment info first
        supabase = get_supabase_client()
        comment_result = supabase.table('comments').select("user_id").eq('id', comment_id).execute()
        
        if not comment_result.data:
            raise HTTPException(status_code=404, detail="Bình luận không tồn tại")
        
        user_id = comment_result.data[0]['user_id']
        return await social_manager.delete_comment(comment_id, user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin delete comment error: {e}")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi xóa bình luận")

@app.get("/api/admin/social-stats")
async def get_social_stats_admin(
    days: int = 30,
    admin_user: UserWithWallet = Depends(require_admin)
):
    """Thống kê mạng xã hội (admin)"""
    try:
        supabase = get_supabase_client()
        
        # Get basic stats
        posts_total = supabase.table('posts').select("id", count="exact").execute()
        comments_total = supabase.table('comments').select("id", count="exact").execute()
        follows_total = supabase.table('follows').select("follower_id", count="exact").execute()
        
        # Get recent activity
        from datetime import datetime, timedelta
        recent_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        posts_recent = supabase.table('posts').select("id", count="exact").gte('created_at', recent_date).execute()
        comments_recent = supabase.table('comments').select("id", count="exact").gte('created_at', recent_date).execute()
        follows_recent = supabase.table('follows').select("follower_id", count="exact").gte('followed_at', recent_date).execute()
        
        # Get top users by posts
        top_posters = supabase.table('posts').select(
            "user_id, users!posts_user_id_fkey(full_name, email)"
        ).execute()
        
        # Count posts per user
        user_post_counts = {}
        for post in top_posters.data:
            user_id = post['user_id']
            user_info = post['users']
            if user_id not in user_post_counts:
                user_post_counts[user_id] = {
                    'count': 0,
                    'user_info': user_info
                }
            user_post_counts[user_id]['count'] += 1
        
        # Sort by post count
        top_posters_sorted = sorted(
            user_post_counts.items(), 
            key=lambda x: x[1]['count'], 
            reverse=True
        )[:10]
        
        return {
            "total_stats": {
                "posts": posts_total.count or 0,
                "comments": comments_total.count or 0,
                "follows": follows_total.count or 0
            },
            "recent_activity": {
                f"posts_last_{days}_days": posts_recent.count or 0,
                f"comments_last_{days}_days": comments_recent.count or 0,
                f"follows_last_{days}_days": follows_recent.count or 0
            },
            "top_posters": [
                {
                    "user_id": user_id,
                    "posts_count": data['count'],
                    "full_name": data['user_info'].get('full_name'),
                    "email": data['user_info'].get('email')
                }
                for user_id, data in top_posters_sorted
            ]
        }
        
    except Exception as e:
        logger.error(f"Get social stats error: {e}")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi lấy thống kê mạng xã hội")

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
# TEMPLATE ROUTES (HTML pages)
# ================================

# ================================
# REMOVED: HTML TEMPLATE ROUTES
# All frontend pages are now handled by Next.js
# Backend only provides API endpoints
# ================================

# ================================
# WEBSOCKET FOR REAL-TIME CHAT
# ================================

# ================================
# WEBSOCKET FOR REAL-TIME CHAT
# ================================

@app.websocket("/ws/chat")
async def chat_websocket(
    websocket: WebSocket, 
    user_id: str = Query(...)
):
    """WebSocket endpoint for real-time chat - Using cookie-based session authentication"""
    try:
        # Parse cookies from WebSocket headers
        cookies = parse_cookies_from_websocket(websocket)
        session_id = cookies.get('session_id')
        
        # Verify session exists and is valid
        if not session_id:
            logger.warning("No session_id found in WebSocket cookies")
            await websocket.close(code=1008, reason="Authentication failed - No session")
            return
        
        # Verify user authentication using session
        session = await auth_manager.get_session(session_id)
        if not session or session['user_id'] != user_id:
            logger.warning(f"Invalid session for user {user_id}")
            await websocket.close(code=1008, reason="Authentication failed - Invalid session")
            return
        
        # Connect user to chat manager
        await chat_manager.connection_manager.connect(websocket, user_id)
        
        # Get user info for chat
        supabase = get_supabase_client()
        user_info = supabase.table("users")\
            .select("full_name, email")\
            .eq("id", user_id)\
            .execute()
        
        user_name = "Unknown User"
        if user_info.data:
            user_name = user_info.data[0].get("full_name") or user_info.data[0].get("email")
        
        logger.info(f"WebSocket connected for user: {user_name} (ID: {user_id})")
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_json()
                event_type = data.get("type")
                
                # Extend session on activity (using session_id from cookie)
                await auth_manager.extend_session(session_id)
                
                if event_type == "message":
                    # Handle chat message
                    message_data = data.get("data")
                    
                    message = ChatMessage(
                        conversation_id=message_data.get("conversation_id"),
                        sender_id=user_id,
                        content=message_data.get("content"),
                        message_type=message_data.get("message_type", "text"),
                        metadata=message_data.get("metadata")
                    )
                    
                    # Send message through chat manager
                    sent_message = await chat_manager.send_message(message)
                    
                    # Send confirmation back to sender
                    await websocket.send_json({
                        "type": "message_sent",
                        "data": {
                            "id": sent_message.id,
                            "conversation_id": sent_message.conversation_id,
                            "created_at": sent_message.created_at.isoformat()
                        }
                    })
                
                elif event_type == "typing":
                    # Handle typing indicators
                    conversation_id = data.get("conversation_id")
                    is_typing = data.get("is_typing", False)
                    
                    await chat_manager.handle_typing_indicator(
                        user_id, conversation_id, is_typing, user_name
                    )
                
                elif event_type == "join_conversation":
                    # Handle joining a conversation (for group chats)
                    conversation_id = data.get("conversation_id")
                    # Add user to conversation participants if not already
                    # Implementation here...
                    pass
                
                elif event_type == "ping":
                    # Handle keep-alive ping
                    await websocket.send_json({"type": "pong"})
                    
        except Exception as e:
            logger.error(f"WebSocket error for user {user_id}: {e}")
        
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        await websocket.close(code=1011, reason="Server error")
    
    finally:
        # Disconnect user from chat manager
        chat_manager.connection_manager.disconnect(websocket, user_id)

# ================================
# CHAT API ENDPOINTS
# ================================

# ================================
# CHAT API ENDPOINTS - OPTIMIZED
# ================================

@app.post("/api/chat/conversations")
async def create_conversation(
    request: CreateConversationRequest,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Create a new conversation - Optimized for production"""
    try:
        conversation = await chat_manager.create_conversation(
            created_by=current_user.id,
            participant_ids=request.participant_ids,
            name=request.name
        )
        
        return {
            "success": True,
            "conversation": {
                "id": conversation.id,
                "name": conversation.name,
                "is_group": conversation.is_group,
                "participant_ids": conversation.participant_ids,
                "created_by": conversation.created_by,
                "created_at": conversation.created_at.isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.get("/api/chat/conversations")
async def get_user_conversations(
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Get all conversations for current user - Optimized with caching"""
    try:
        conversations = await chat_manager.get_user_conversations(current_user.id)
        
        return {
            "success": True,
            "conversations": conversations,
            "total": len(conversations)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.get("/api/chat/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100, description="Number of messages to fetch"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Get messages for a conversation - Optimized with pagination"""
    try:
        messages = await chat_manager.get_conversation_messages(
            conversation_id=conversation_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "messages": messages,
            "total": len(messages),
            "limit": limit,
            "offset": offset,
            "has_more": len(messages) == limit  # Indicate if there are more messages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.post("/api/chat/conversations/{conversation_id}/messages")
async def send_message_http(
    conversation_id: str,
    request: SendMessageRequest,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Send a message via HTTP (fallback for WebSocket) - Production ready"""
    try:
        message = ChatMessage(
            conversation_id=conversation_id,
            sender_id=current_user.id,
            content=request.content,
            message_type=request.message_type,
            metadata=request.metadata
        )
        
        sent_message = await chat_manager.send_message(message)
        
        return {
            "success": True,
            "message": {
                "id": sent_message.id,
                "conversation_id": sent_message.conversation_id,
                "sender_id": sent_message.sender_id,
                "content": sent_message.content,
                "message_type": sent_message.message_type,
                "metadata": sent_message.metadata,
                "created_at": sent_message.created_at.isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.get("/api/chat/conversations/{conversation_id}/participants")
async def get_conversation_participants(
    conversation_id: str,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Get participants in a conversation"""
    try:
        # Use service key to bypass RLS restrictions
        supabase = get_supabase_client(use_service_key=True)
        
        # Verify user is participant
        participant_check = supabase.table("participants")\
            .select("id")\
            .eq("conversation_id", conversation_id)\
            .eq("user_id", current_user.id)\
            .execute()
        
        if not participant_check.data:
            raise HTTPException(status_code=403, detail="Not authorized to view this conversation")
        
        # Get all participants with user info
        participants_result = supabase.table("participants")\
            .select("""
                user_id, is_admin, joined_at,
                users!participants_user_id_fkey(full_name, email, avatar_url)
            """)\
            .eq("conversation_id", conversation_id)\
            .eq("is_active", True)\
            .execute()
        
        participants = []
        for p in participants_result.data:
            user_info = p.get("users", {})
            participants.append({
                "user_id": p["user_id"],
                "is_admin": p["is_admin"],
                "joined_at": p["joined_at"],
                "name": user_info.get("full_name") or user_info.get("email", "Unknown"),
                "avatar_url": user_info.get("avatar_url")
            })
        
        return {
            "success": True,
            "participants": participants,
            "total": len(participants)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.post("/api/chat/conversations/{conversation_id}/read")
async def mark_messages_as_read(
    conversation_id: str,
    request: MarkMessagesAsReadRequest,
    current_user: UserWithWallet = Depends(get_current_user)
):
    """Mark messages as read in a conversation"""
    try:
        # Use service key to bypass RLS restrictions
        supabase = get_supabase_client(use_service_key=True)
        
        # Verify user is participant
        participant_check = supabase.table("participants")\
            .select("id")\
            .eq("conversation_id", conversation_id)\
            .eq("user_id", current_user.id)\
            .execute()
        
        if not participant_check.data:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Get messages to mark as read
        query = supabase.table("messages")\
            .select("id")\
            .eq("conversation_id", conversation_id)\
            .neq("sender_id", current_user.id)  # Don't mark own messages
        
        if request.message_id:
            # Mark up to specific message
            query = query.lte("created_at", 
                supabase.table("messages")
                .select("created_at")
                .eq("id", request.message_id)
                .execute().data[0]["created_at"]
            )
        
        messages = query.execute().data
        
        # Create read receipts
        read_receipts = []
        for msg in messages:
            read_receipts.append({
                "message_id": msg["id"],
                "user_id": current_user.id,
                "read_at": datetime.now().isoformat()
            })
        
        if read_receipts:
            supabase.table("message_read_receipts")\
                .upsert(read_receipts, on_conflict="message_id,user_id")\
                .execute()
        
        return {
            "success": True,
            "marked_as_read": len(read_receipts)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

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
    """Lấy dữ liệu giá cổ phiếu và chỉ báo kỹ thuật"""
    # logger.info(f"Stock data request: symbol={request_data.symbol}, start_date={request_data.start_date}, end_date={request_data.end_date}")
    try:
        # Load Vietnam stock data
        df = load_stock_data_vn(request_data.symbol, "2011-01-01", datetime.now().strftime('%Y-%m-%d'))
        df = add_technical_indicators_vnquant(df)

        # Clean the dataframe for JSON serialization
        data_records = clean_dataframe_for_json(df)
        
        return {
            'success': True,
            'data': data_records,
            'columns': list(df.columns),
            'symbol': request_data.symbol,
            'date_range': {
                'start': '2011-01-01',
                'end': datetime.now().strftime('%Y-%m-%d')
            },
            'authenticated': current_user is not None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.post("/api/technical_signals")
@check_balance_and_track("technical_analysis")
async def get_technical_signals(
    request_data: TechnicalSignalsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Phát hiện tín hiệu kỹ thuật"""
    try:
        # Load and analyze data
        df = load_stock_data_yf(request_data.symbol, request_data.asset_type, "2000-01-01", datetime.now().strftime('%Y-%m-%d'))
        df = add_technical_indicators_yf(df)
        
        # Detect signals
        signals = detect_signals(df)
        
        # Clean signals data if it contains DataFrames or problematic values
        if isinstance(signals, dict):
            for key, value in signals.items():
                if isinstance(value, pd.DataFrame):
                    signals[key] = clean_dataframe_for_json(value)
        
        return {
            'success': True,
            'signals': signals,
            'symbol': request_data.symbol,
            'generated_at': datetime.now().isoformat(),
            'authenticated': current_user is not None
        }
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
@check_balance_and_track("news_analysis")
async def get_news(
    request_data: NewsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Lấy tin tức về cổ phiếu từ nhiều nguồn"""
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
        
        # Vietnamese stocks - prioritize Vietnamese sources
        # is_vietnamese_stock = not any(char in symbol for char in ['.', ':']) or symbol.endswith('.VN')
        
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
@check_balance_and_track("portfolio_optimization")
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

@app.post("/api/insights")
@check_balance_and_track("ai_insights")
async def get_insights_api(
    request_data: InsightsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Lấy phân tích AI từ dữ liệu kỹ thuật và tin tức (Legacy - non-streaming)"""
    try:
        # Set default dates if not provided
        start_date = request_data.start_date or (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        end_date = request_data.end_date or datetime.now().strftime('%Y-%m-%d')
        
        # Get AI insights
        response_ta, response_news, response_combined = get_insights(
            ticker=request_data.ticker,
            asset_type=request_data.asset_type,
            start_date=start_date,
            end_date=end_date,
            look_back_days=request_data.look_back_days
        )
        
        # Extract text content from the responses
        technical_analysis = response_ta.text if hasattr(response_ta, 'text') else str(response_ta)
        news_analysis = response_news.text if hasattr(response_news, 'text') else str(response_news)
        combined_analysis = response_combined.text if hasattr(response_combined, 'text') else str(response_combined)
        
        return {
            'success': True,
            'ticker': request_data.ticker,
            'technical_analysis': technical_analysis,
            'news_analysis': news_analysis,
            'combined_analysis': combined_analysis,
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'date_range': {'start': start_date, 'end': end_date},
                'look_back_days': request_data.look_back_days,
                'authenticated': current_user is not None
            }
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Server xử lý lỗi. Vui lòng thử lại.")

@app.post("/api/insights/stream")
@check_balance_and_track_streaming("ai_insights")
async def get_insights_stream_api(
    request_data: InsightsRequest,
    current_user: Optional[UserWithWallet] = Depends(get_optional_user),
    request: Request = None
):
    """Lấy phân tích AI với streaming response (Server-Sent Events)"""
    
    # Set default dates if not provided
    start_date = request_data.start_date or (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    end_date = request_data.end_date or datetime.now().strftime('%Y-%m-%d')
    
    async def generate_insights():
        try:
            # Initialize metadata at the start
            import json
            metadata = {
                'ticker': request_data.ticker,
                'generated_at': datetime.now().isoformat(),
                'date_range': {'start': start_date, 'end': end_date},
                'look_back_days': request_data.look_back_days,
                'authenticated': current_user is not None
            }
            
            # Send metadata first
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"
            
            # Generate streaming insights
            for chunk in get_insights_streaming(
                ticker=request_data.ticker,
                asset_type=request_data.asset_type,
                start_date=start_date,
                end_date=end_date,
                look_back_days=request_data.look_back_days
            ):
                yield chunk
                # Add small delay to make streaming more visible
                import asyncio
                await asyncio.sleep(0.01)
                
        except Exception:
            yield f"data: {{\"type\": \"error\", \"message\": \"Server xử lý lỗi. Vui lòng thử lại.\"}}\n\n"
    
    return StreamingResponse(
        generate_insights(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# @app.post("/api/stock_analysis")
# @track_service("stock_analysis")
# async def stock_analysis_api(
#     request_data: StockAnalysisRequest,
#     current_user: Optional[UserWithWallet] = Depends(get_optional_user),
#     request: Request = None
# ):
#     """Phân tích và dự báo cổ phiếu bằng Prophet"""
#     try:
#         # Log request details
#         # logger.info(f"Stock analysis request: symbol={request_data.symbol}, start_date={request_data.start_date}, forecast_periods={request_data.forecast_periods}")
        
#         # Validate inputs
#         if not request_data.symbol:
#             # logger.warning("Empty symbol provided")
#             raise HTTPException(status_code=400, detail="Vui lòng nhập mã cổ phiếu")
        
#         # Clean symbol
#         symbol = request_data.symbol.upper().strip()
#         # logger.info(f"Analyzing stock: {symbol}")
        
#         # Perform stock analysis (matching the function signature)
#         result = analyze_stock(symbol, request_data.start_date, request_data.forecast_periods)
        
#         # Add metadata to result
#         if result.get('success'):
#             result['metadata'] = {
#                 'analysis_date': datetime.now().isoformat(),
#                 'model_type': 'Prophet',
#                 'forecast_periods': request_data.forecast_periods,
#                 'authenticated': current_user is not None
#             }
#             # logger.info(f"Stock analysis successful for {symbol}")
#         else:
#             logger.warning(f"Stock analysis failed for {symbol}: {result.get('error', 'Unknown error')}")
        
#         return result
        
#     except HTTPException as e:
#         logger.error(f"HTTP Exception in stock analysis: {e.detail}")
#         raise
#     except Exception as e:
#         logger.error(f"Unexpected error in stock analysis: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Lỗi khi phân tích cổ phiếu: {str(e)}")

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
    
    return {
        "success": True,
        "status": {
            "database": db_status,
            "chat_system": "active" if chat_manager else "inactive",
            "performance": performance_monitor.get_stats(),
            "timestamp": datetime.now().isoformat()
        }
    }

if __name__ == '__main__':
    uvicorn.run(
        "app_fastapi:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        access_log=True,
        log_level="info"
    )














