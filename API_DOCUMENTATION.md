# 📖 FRM-AI API Documentation

## Tổng quan
FRM-AI (Financial Risk Management with AI) là một hệ thống quản lý rủi ro tài chính được xây dựng trên FastAPI và Supabase, cung cấp các chức năng phân tích tài chính với AI, quản lý danh mục đầu tư, và hệ thống mạng xã hội cho nhà đầu tư.

**Base URL:** `http://localhost:8000` (Development) | `https://your-domain.com` (Production)

**API Version:** 3.0.0

---

## 🔐 Authentication

Hệ thống sử dụng **Session Cookies** để xác thực thay vì JWT tokens. Session được lưu trữ trong database và được quản lý tự động qua HTTP cookies.

**Cookie Name:** `session_id`
**Cookie Properties:**
- **HttpOnly:** true (không thể truy cập từ JavaScript)
- **SameSite:** lax
- **Secure:** false (development), true (production)
- **Max-Age:** 86400 seconds (24 hours)

### Authentication Endpoints

#### 1. Đăng ký tài khoản
```http
POST /api/auth/register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "Nguyễn Văn A",
  "phone": "0901234567"
}
```

**Response:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "Nguyễn Văn A",
    "phone": "0901234567",
    "role": "user",
    "is_verified": false,
    "balance": 0,
    "locked_balance": 0,
    "total_earned": 0,
    "total_spent": 0
  },
  "message": "Đăng ký thành công"
}
```

**Response Headers:**
```
Set-Cookie: session_id=<session_value>; HttpOnly; Max-Age=86400; SameSite=lax; Path=/
```

**Note:** Session cookie được set tự động trong response headers. `session_id` không xuất hiện trong response body vì lý do bảo mật.
```

#### 2. Đăng nhập
```http
POST /api/auth/login
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "Nguyễn Văn A",
    "balance": 1000000
  },
  "message": "Đăng nhập thành công"
}
```

**Response Headers:**
```
Set-Cookie: session_id=<session_value>; HttpOnly; Max-Age=86400; SameSite=lax; Path=/
```

**Note:** Session cookie được set tự động trong response headers. `session_id` không xuất hiện trong response body vì lý do bảo mật.
```

#### 3. Đăng xuất
```http
POST /api/auth/logout
```

**Headers:** Session cookie (automatic)

**Response:**
```json
{
  "message": "Đã đăng xuất"
}
```

**Response Headers:**
```
Set-Cookie: session_id=; HttpOnly; Max-Age=0; Path=/
```

**Note:** Session cookie được xóa tự động trong response headers.
```

#### 4. Lấy thông tin user hiện tại
```http
GET /api/auth/me
```

**Headers:** Session cookie (automatic)

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Nguyễn Văn A",
  "phone": "0901234567",
  "balance": 1000000,
  "locked_balance": 0,
  "total_earned": 5000000,
  "total_spent": 4000000
}
```

#### 5. Cập nhật thông tin cá nhân
```http
PUT /api/auth/profile
```

**Headers:** Session cookie (automatic)

**Request Body:**
```json
{
  "full_name": "Nguyễn Văn B",
  "phone": "0909876543",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

#### 6. Đổi mật khẩu
```http
POST /api/auth/change-password
```

**Headers:** Session cookie (automatic)

**Request Body:**
```json
{
  "current_password": "old_password",
  "new_password": "new_password"
}
```

---

## 💰 Wallet Management

### Wallet Endpoints

#### 1. Lấy thông tin ví
```http
GET /api/wallet
```

**Headers:** Session cookie (automatic)

**Response:**
```json
{
  "user_id": "uuid",
  "balance": 1000000,
  "locked_balance": 0,
  "total_earned": 5000000,
  "total_spent": 4000000,
  "last_transaction_at": "2024-01-01T00:00:00Z"
}
```

#### 2. Lấy lịch sử giao dịch
```http
GET /api/wallet/transactions?limit=50&offset=0&transaction_type=deposit
```

**Headers:** Session cookie (automatic)

**Query Parameters:**
- `limit` (int, optional): Số lượng giao dịch (default: 50)
- `offset` (int, optional): Bỏ qua (default: 0)
- `transaction_type` (string, optional): Loại giao dịch

**Response:**
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "amount": 100000,
    "transaction_type": "deposit",
    "description": "Nạp tiền vào ví",
    "status": "completed",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### 3. Chuyển tiền cho user khác
```http
POST /api/wallet/transfer
```

**Headers:** Session cookie (automatic)

**Request Body:**
```json
{
  "recipient_email": "recipient@example.com",
  "amount": 50000,
  "description": "Chuyển tiền"
}
```

#### 4. Lấy thống kê ví
```http
GET /api/wallet/stats?days=30
```

**Headers:** Session cookie (automatic)

**Query Parameters:**
- `days` (int, optional): Số ngày thống kê (default: 30)

**Response:**
```json
{
  "total_income": 1000000,
  "total_expense": 500000,
  "transaction_count": 25,
  "daily_stats": [
    {
      "date": "2024-01-01",
      "income": 100000,
      "expense": 50000
    }
  ]
}
```

---

## 📦 Package Management

### Package Endpoints

#### 1. Lấy danh sách gói dịch vụ
```http
GET /api/packages?include_inactive=false
```

**Query Parameters:**
- `include_inactive` (bool, optional): Bao gồm gói không hoạt động (default: false)

**Response:**
```json
[
  {
    "id": 1,
    "name": "Gói Cơ Bản",
    "description": "Gói dịch vụ cơ bản",
    "price": 99000,
    "duration_days": 30,
    "features": ["Feature 1", "Feature 2"],
    "is_active": true
  }
]
```

#### 2. Lấy thông tin gói dịch vụ
```http
GET /api/packages/{package_id}
```

**Response:** Thông tin chi tiết 1 gói dịch vụ

#### 3. Mua gói dịch vụ
```http
POST /api/packages/{package_id}/purchase
```

**Headers:** Session cookie (automatic)

**Response:**
```json
{
  "message": "Mua gói thành công",
  "user_package_id": "uuid",
  "expires_at": "2024-02-01T00:00:00Z"
}
```

#### 4. Lấy danh sách gói đã mua
```http
GET /api/my-packages?status=active
```

**Headers:** Session cookie (automatic)

**Query Parameters:**
- `status` (string, optional): Trạng thái gói (active, expired, cancelled)

#### 5. Hủy gói dịch vụ
```http
POST /api/packages/{user_package_id}/cancel
```

**Headers:** Session cookie (automatic)

---

## 🔔 Notification Management

### Notification Endpoints

#### 1. Lấy danh sách thông báo
```http
GET /api/notifications?limit=50&offset=0&unread_only=false
```

**Headers:** Session cookie (automatic)

**Query Parameters:**
- `limit` (int): Số lượng thông báo
- `offset` (int): Bỏ qua
- `unread_only` (bool): Chỉ lấy thông báo chưa đọc

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "Thông báo mới",
    "message": "Nội dung thông báo",
    "type": "info",
    "is_read": false,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### 2. Đánh dấu thông báo đã đọc
```http
POST /api/notifications/{notification_id}/read
```

**Headers:** Session cookie (automatic)

#### 3. Đánh dấu tất cả thông báo đã đọc
```http
POST /api/notifications/mark-all-read
```

**Headers:** Session cookie (automatic)

#### 4. Xóa thông báo
```http
DELETE /api/notifications/{notification_id}
```

**Headers:** Session cookie (automatic)

#### 5. Lấy số lượng thông báo chưa đọc
```http
GET /api/notifications/unread-count
```

**Headers:** Session cookie (automatic)

**Response:**
```json
{
  "unread_count": 5
}
```

---

## 📊 Financial Analysis APIs

### Stock Data & Analysis

#### 1. Lấy dữ liệu giá cổ phiếu
```http
POST /api/stock_data
```

**Request Body:**
```json
{
  "symbol": "VCB",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "date": "2024-01-01",
      "open": 85000,
      "high": 87000,
      "low": 84000,
      "close": 86000,
      "volume": 1000000,
      "sma_20": 85500,
      "rsi": 55.5
    }
  ],
  "columns": ["date", "open", "high", "low", "close", "volume", "sma_20", "rsi"],
  "symbol": "VCB",
  "authenticated": true
}
```

#### 2. Phát hiện tín hiệu kỹ thuật
```http
POST /api/technical_signals
```

**Request Body:**
```json
{
  "symbol": "VCB"
}
```

**Response:**
```json
{
  "success": true,
  "signals": {
    "buy_signals": ["Golden Cross", "RSI Oversold"],
    "sell_signals": [],
    "neutral_signals": ["MACD Convergence"],
    "signal_strength": "STRONG_BUY"
  },
  "symbol": "VCB",
  "generated_at": "2024-01-01T00:00:00Z"
}
```

#### 3. Tính điểm cơ bản
```http
POST /api/fundamental_score
```

**Request Body:**
```json
{
  "tickers": ["VCB.VN", "BID.VN", "CTG.VN"]
}
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "ticker": "VCB.VN",
      "score": 85,
      "ranking": "A",
      "metrics": {
        "pe_ratio": 12.5,
        "pb_ratio": 1.8,
        "roe": 18.5
      }
    }
  ],
  "total_stocks": 3,
  "evaluated_at": "2024-01-01T00:00:00Z"
}
```

#### 4. Lấy tin tức cổ phiếu
```http
POST /api/news
```

**Request Body:**
```json
{
  "symbol": "VCB",
  "pages": 2,
  "look_back_days": 30,
  "news_sources": ["google"],
  "max_results": 50
}
```

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "title": "VCB công bố kết quả kinh doanh Q4",
      "snippet": "Vietcombank báo lãi 15,000 tỷ đồng...",
      "source": "Google News",
      "link": "https://example.com/news",
      "date": "2024-01-01",
      "sentiment": "positive",
      "relevance_score": 15
    }
  ],
  "symbol": "VCB",
  "metadata": {
    "symbol_type": "vietnamese",
    "search_parameters": {
      "symbol": "VCB",
      "pages": 2,
      "look_back_days": 30,
      "news_sources": ["google"],
      "max_results": 50
    },
    "statistics": {
      "total_articles": 25,
      "sources_used": ["google"],
      "date_range": {
        "from": "2024-01-01",
        "to": "2024-01-31"
      },
      "processing_time": 1.25
    }
  },
  "authenticated": true
}
```

#### 5. Tối ưu hóa danh mục đầu tư
```http
POST /api/optimize_portfolio
```

**Request Body:**
```json
{
  "symbols": ["VCB", "BID", "CTG", "MBB", "TCB"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "investment_amount": 1000000000
}
```

**Response:**
```json
{
  "success": true,
  "optimization_result": {
    "weights": {
      "VCB": 0.3,
      "BID": 0.25,
      "CTG": 0.2,
      "MBB": 0.15,
      "TCB": 0.1
    },
    "expected_return": 0.15,
    "risk": 0.12,
    "sharpe_ratio": 1.25
  },
  "allocation": {
    "VCB": 300000000,
    "BID": 250000000,
    "CTG": 200000000,
    "MBB": 150000000,
    "TCB": 100000000
  }
}
```

#### 6. Tính toán danh mục thủ công
```http
POST /api/calculate_manual_portfolio
```

**Request Body:**
```json
{
  "manual_weights": {
    "VCB": 30,
    "BID": 25,
    "CTG": 20,
    "MBB": 15,
    "TCB": 10
  },
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "investment_amount": 1000000000
}
```

#### 7. Lấy insights AI
```http
POST /api/insights
```

**Request Body:**
```json
{
  "ticker": "VCB",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "look_back_days": 30
}
```

**Response:**
```json
{
  "success": true,
  "ticker": "VCB",
  "technical_analysis": "Cổ phiếu VCB đang trong xu hướng tăng...",
  "news_analysis": "Tin tức gần đây tích cực...",
  "combined_analysis": "Kết hợp phân tích kỹ thuật và tin tức...",
  "metadata": {
    "generated_at": "2024-01-01T00:00:00Z",
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-12-31"
    },
    "look_back_days": 30,
    "authenticated": true
  }
}
```

#### 8. Gửi cảnh báo
```http
POST /api/send_alert
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "subject": "Cảnh báo cổ phiếu VCB",
  "signals": ["Golden Cross", "Volume Breakout"]
}
```

---

## 🔧 Service Usage & Analytics

### Service Usage Endpoints

#### 1. Lấy lịch sử sử dụng dịch vụ
```http
GET /api/service-usage/history?limit=50&offset=0&service_type=stock_analysis&days=30
```

**Headers:** Session cookie (automatic)

#### 2. Lấy thống kê sử dụng dịch vụ
```http
GET /api/service-usage/stats?days=30
```

**Headers:** Session cookie (automatic)

**Response:**
```json
{
  "total_requests": 150,
  "services_used": {
    "stock_analysis": 80,
    "portfolio_optimization": 30,
    "news_analysis": 40
  },
  "daily_usage": [
    {
      "date": "2024-01-01",
      "requests": 10
    }
  ]
}
```

---

## 👑 Admin Endpoints

### Admin Dashboard & Management

#### 1. Dashboard thống kê admin
```http
GET /api/admin/dashboard
```

**Headers:** Session cookie (automatic) - User must have admin role

**Response:**
```json
{
  "users": {
    "total": 1000,
    "active": 800,
    "new_this_month": 50
  },
  "packages": {
    "total_sales": 150000000,
    "active_subscriptions": 300
  },
  "wallet": {
    "total_balance": 5000000000,
    "total_transactions": 25000
  },
  "service_usage": {
    "total_requests": 100000,
    "top_services": ["stock_analysis", "news_analysis"]
  }
}
```

#### 2. Tóm tắt tài chính
```http
GET /api/admin/financial-summary?days=30
```

**Headers:** Session cookie (automatic) - User must have admin role

#### 3. Tạo gói dịch vụ
```http
POST /api/admin/packages
```

**Headers:** Session cookie (automatic) - User must have admin role

**Request Body:**
```json
{
  "name": "Gói Premium",
  "description": "Gói dịch vụ cao cấp",
  "price": 299000,
  "duration_days": 30,
  "features": ["Unlimited analysis", "Priority support"],
  "is_active": true
}
```

#### 4. Cập nhật gói dịch vụ
```http
PUT /api/admin/packages/{package_id}
```

**Headers:** Session cookie (automatic) - User must have admin role

#### 5. Gửi thông báo hàng loạt
```http
POST /api/admin/notifications/broadcast
```

**Headers:** Session cookie (automatic) - User must have admin role

**Request Body:**
```json
{
  "title": "Thông báo hệ thống",
  "message": "Hệ thống sẽ bảo trì từ 2h-4h sáng",
  "type": "system",
  "target_users": "all",
  "send_email": true
}
```

#### 6. Thêm coins cho user
```http
POST /api/admin/wallet/{user_id}/add-coins
```

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "amount": 100000,
  "description": "Thưởng sự kiện"
}
```

#### 7. Dọn dẹp dữ liệu cũ
```http
POST /api/admin/cleanup
```

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "days_to_keep": 365
}
```

---

## 🛠️ System & Health Check

### System Endpoints

#### 1. Health check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "3.0.0",
  "environment": "production"
}
```

#### 2. API info
```http
GET /api
```

**Response:**
```json
{
  "name": "FRM-AI Financial Risk Management API",
  "version": "3.0.0",
  "framework": "FastAPI + Supabase",
  "description": "Hệ thống quản lý rủi ro tài chính với AI và Blockchain",
  "features": [...],
  "endpoints": {...},
  "docs": "/docs",
  "redoc": "/redoc"
}
```

#### 3. System metrics
```http
GET /api/system/metrics
```

**Response:**
```json
{
  "success": true,
  "metrics": {
    "uptime": 86400,
    "total_requests": 1000,
    "average_response_time": 0.25,
    "requests_per_minute": 10.5
  }
}
```

#### 4. System status
```http
GET /api/system/status
```

**Response:**
```json
{
  "success": true,
  "status": {
    "database": "connected",
    "chat_system": "active",
    "performance": {...},
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

---

## 🔒 GDPR & Data Privacy

### User Data Management

#### 1. Xuất dữ liệu user
```http
GET /api/user/export-data
```

**Headers:** Session cookie (automatic)

**Response:** File ZIP chứa tất cả dữ liệu của user

#### 2. Xóa tài khoản và dữ liệu
```http
DELETE /api/user/delete-account
```

**Headers:** Session cookie (automatic)

**Response:**
```json
{
  "message": "Tài khoản đã được xóa thành công"
}
```

---

## 🔧 Request/Response Headers

### Common Request Headers
- `Cookie: session_id=<session_id>` - Session authentication
- `Content-Type: application/json` - JSON content
- `Accept: application/json` - Accept JSON response

### Common Response Headers
- `X-Process-Time` - Request processing time
- `X-Request-Count` - Total request count
- `X-API-Version` - API version
- `Cache-Control` - Caching policy

---

## 📝 Notes

### Rate Limiting
- Không có rate limiting cụ thể được implement
- Khuyến nghị implement rate limiting trong production

### Pagination
- Hầu hết endpoints hỗ trợ `limit` và `offset`
- Default limit thường là 50
- Maximum limit khuyến nghị: 100

### Service Tracking
- Các API financial analysis được track sử dụng dịch vụ
- Cần có gói dịch vụ hoặc coins để sử dụng

### Authentication Levels
1. **Public**: Không cần authentication
2. **User**: Cần session cookie
3. **Admin**: Cần session cookie với role admin

---

## 🔗 Interactive Documentation

- **Swagger UI:** `/docs`
- **ReDoc:** `/redoc`

Sử dụng Swagger UI để test các API endpoints trực tiếp từ browser.
