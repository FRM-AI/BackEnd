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

## � Insights History Management

### Insights History Endpoints

Hệ thống lưu trữ lịch sử phân tích insights của người dùng với giới hạn 10 phân tích gần nhất cho mỗi loại phân tích. Dữ liệu được lưu trong Supabase và tự động xóa phân tích cũ nhất khi vượt quá giới hạn.

#### 1. Lấy lịch sử phân tích (/api/insights-history để lấy toàn bộ lịch sử)
```http
GET /api/insights-history?limit=50&offset=0&analysis_type=technical_analysis&ticker=VCB
```

**Headers:** Session cookie (automatic)

**Query Parameters:**
- `limit` (int, optional): Số lượng kết quả tối đa (default: 50)
- `offset` (int, optional): Vị trí bắt đầu (default: 0)
- `analysis_type` (string, optional): Lọc theo loại phân tích
  - `technical_analysis`: Phân tích kỹ thuật
  - `news_analysis`: Phân tích tin tức
  - `proprietary_trading_analysis`: Phân tích giao dịch tự doanh
  - `foreign_trading_analysis`: Phân tích giao dịch khối ngoại
  - `shareholder_trading_analysis`: Phân tích giao dịch cổ đông
  - `intraday_match_analysis`: Phân tích khớp lệnh trong phiên
- `ticker` (string, optional): Lọc theo mã cổ phiếu (VD: VCB, BID)

**Response:**
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "ticker": "VCB",
    "asset_type": "stock",
    "analysis_type": "technical_analysis",
    "content": "Phân tích kỹ thuật chi tiết về cổ phiếu VCB...",
    "metadata": {
      "date_range": {
        "start": "2024-01-01",
        "end": "2024-12-31"
      },
      "generated_at": "2024-01-15T10:30:00Z"
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

**Features:**
- Tự động lưu phân tích từ các streaming API
- Giới hạn 10 phân tích gần nhất cho mỗi `analysis_type`
- Phân tích cũ nhất tự động bị xóa khi thêm phân tích mới
- Hỗ trợ filter theo ticker và analysis_type
- Pagination với limit và offset

#### 2. Lấy chi tiết một phân tích
```http
GET /api/insights-history/{insight_id}
```

**Headers:** Session cookie (automatic)

**Path Parameters:**
- `insight_id` (string, required): ID của phân tích

**Response:**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "ticker": "VCB",
  "asset_type": "stock",
  "analysis_type": "news_analysis",
  "content": "Phân tích tin tức chi tiết về VCB trong 30 ngày qua...",
  "metadata": {
    "look_back_days": 30,
    "generated_at": "2024-01-15T14:00:00Z"
  },
  "created_at": "2024-01-15T14:00:00Z",
  "updated_at": "2024-01-15T14:00:00Z"
}
```

**Error Response (404):**
```json
{
  "detail": "Không tìm thấy phân tích"
}
```

#### 3. Xóa một phân tích
```http
DELETE /api/insights-history/{insight_id}
```

**Headers:** Session cookie (automatic)

**Path Parameters:**
- `insight_id` (string, required): ID của phân tích cần xóa

**Response:**
```json
{
  "message": "Đã xóa phân tích thành công"
}
```

**Error Response (404):**
```json
{
  "detail": "Không tìm thấy phân tích"
}
```

#### 4. Xóa tất cả lịch sử phân tích
```http
DELETE /api/insights-history
```

**Headers:** Session cookie (automatic)

**Response:**
```json
{
  "message": "Đã xóa 25 phân tích",
  "count": 25
}
```

**Features:**
- Xóa toàn bộ lịch sử phân tích của user
- Không thể khôi phục sau khi xóa
- Trả về số lượng phân tích đã xóa

#### 5. Lấy thống kê lịch sử phân tích
```http
GET /api/insights-history/stats
```

**Headers:** Session cookie (automatic)

**Response:**
```json
{
  "total_insights": 45,
  "by_analysis_type": {
    "technical_analysis": 12,
    "news_analysis": 15,
    "proprietary_trading_analysis": 8,
    "foreign_trading_analysis": 5,
    "shareholder_trading_analysis": 3,
    "intraday_match_analysis": 2
  },
  "by_ticker": {
    "VCB": 15,
    "BID": 12,
    "CTG": 10,
    "TCB": 5,
    "MBB": 3
  },
  "most_analyzed_ticker": {
    "ticker": "VCB",
    "count": 15
  },
  "most_used_analysis": {
    "type": "news_analysis",
    "count": 15
  }
}
```

**Features:**
- Thống kê tổng số phân tích
- Phân loại theo loại phân tích
- Phân loại theo mã cổ phiếu
- Hiển thị cổ phiếu được phân tích nhiều nhất
- Hiển thị loại phân tích được sử dụng nhiều nhất

### Cách hoạt động của Insights History

1. **Tự động lưu**: Mỗi khi user thực hiện phân tích qua các streaming API, hệ thống tự động lưu kết quả vào lịch sử
2. **Giới hạn 10 phân tích**: Mỗi `analysis_type` chỉ lưu tối đa 10 phân tích gần nhất
3. **Auto cleanup**: Database trigger tự động xóa phân tích cũ nhất khi thêm phân tích mới
4. **Row Level Security**: User chỉ có thể xem và quản lý phân tích của mình
5. **Metadata linh hoạt**: Mỗi phân tích có metadata riêng (date_range, look_back_days, etc.)

### Các loại phân tích được lưu

| Analysis Type | Mô tả | TTL Cache |
|---------------|-------|-----------|
| `technical_analysis` | Phân tích kỹ thuật | 6 giờ |
| `news_analysis` | Phân tích tin tức | 2 giờ |
| `proprietary_trading_analysis` | Phân tích giao dịch tự doanh | 4 giờ |
| `foreign_trading_analysis` | Phân tích giao dịch khối ngoại | 4 giờ |
| `shareholder_trading_analysis` | Phân tích giao dịch cổ đông | 8 giờ |
| `intraday_match_analysis` | Phân tích khớp lệnh trong phiên | 12 giờ |

### Database Schema

```sql
CREATE TABLE insights_history (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    ticker VARCHAR(20) NOT NULL,
    asset_type VARCHAR(20) NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_insights_history_user_created ON insights_history(user_id, created_at DESC);
CREATE INDEX idx_insights_history_user_ticker_type ON insights_history(user_id, ticker, analysis_type, created_at DESC);
```

### Example Usage

**Lấy tất cả phân tích :**
```http
GET /api/insights-history
```

**Lấy 20 phân tích tin tức gần nhất:**
```http
GET /api/insights-history?analysis_type=news_analysis&limit=20
```

**Xem thống kê tổng quan:**
```http
GET /api/insights-history/stats
```

---

## �🔔 Notification Management

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
  "asset_type": "stock",
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
  "authenticated": true,
  "from_cache": false,
  "cache_ttl": 1800
}
```

**Features:**
- Sử dụng Redis cache với TTL 30 phút
- Nếu có cache, trả về ngay với `from_cache: true`
- Cache key: `stock_data:{symbol}:{asset_type}:{start_date}:{end_date}`

#### 2. Phát hiện tín hiệu kỹ thuật
```http
POST /api/technical_signals
```

**Request Body:**
```json
{
  "symbol": "VCB",
  "asset_type": "stock"
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
  "generated_at": "2024-01-01T00:00:00Z",
  "from_cache": false,
  "cache_ttl": 3600
}
```

**Features:**
- Sử dụng Redis cache với TTL 1 giờ
- Nếu có cache, trả về ngay với `from_cache: true`
- Cache key: `technical_signals:{symbol}:{asset_type}`

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

#### 4. Lấy tin tức cổ phiếu (Streaming)
```http
POST /api/news
```

**Headers:**
- `Accept: text/event-stream` (để nhận streaming response, mặc định)
- Session cookie (automatic)

**Request Body:**
```json
{
  "symbol": "VCB",
  "asset_type": "stock",
  "pages": 2,
  "look_back_days": 30,
  "news_sources": ["google"],
  "max_results": 50
}
```

**Response (Streaming - Default):**
```
data: {"type": "status", "message": "Đang tìm kiếm tin tức...", "progress": 10}

data: {"type": "news_item", "data": {"title": "VCB công bố kết quả Q4", "snippet": "...", "source": "Google News"}}

data: {"type": "complete", "total_articles": 25}
```

**Response (Non-Streaming):**
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
  "from_cache": false,
  "cache_ttl": 3600,
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

**Features:**
- Mặc định trả về streaming response
- Sử dụng Redis cache với TTL 1 giờ
- Cache key: `news:{symbol}:{asset_type}:{look_back_days}`
- Nếu có cache, trả về ngay với `from_cache: true`
- Hỗ trợ cả streaming và non-streaming response

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

#### 7. Phân tích kỹ thuật (Streaming)
```http
POST /api/technical-analysis/stream
```

**Headers:**
- `Accept: text/event-stream` (để nhận streaming response)
- Session cookie (automatic)

**Request Body:**
```json
{
  "ticker": "VCB",
  "asset_type": "stock",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

**Response (Server-Sent Events):**
```
data: {"type": "metadata", "data": {"ticker": "VCB", "analysis_type": "technical_analysis"}}

data: {"type": "status", "message": "Đang tải dữ liệu chứng khoán...", "progress": 10}

data: {"type": "section_start", "section": "technical_analysis", "title": "Phân Tích Kỹ Thuật"}

data: {"type": "content", "section": "technical_analysis", "text": "Cổ phiếu VCB đang trong xu hướng tăng..."}

data: {"type": "section_end", "section": "technical_analysis"}

data: {"type": "complete", "message": "Phân tích kỹ thuật hoàn tất!", "progress": 100}
```

**Features:**
- Sử dụng Redis cache với TTL 6 giờ
- Phân tích kỹ thuật dựa trên các chỉ báo và tín hiệu
- Cache key: `technical_analysis:{ticker}:{start_date}:{end_date}`

#### 8. Phân tích tin tức (Streaming)
```http
POST /api/news-analysis/stream
```

**Headers:**
- `Accept: text/event-stream` (để nhận streaming response)
- Session cookie (automatic)

**Request Body:**
```json
{
  "ticker": "VCB",
  "asset_type": "stock",
  "look_back_days": 30
}
```

**Response (Server-Sent Events):**
```
data: {"type": "metadata", "data": {"ticker": "VCB", "analysis_type": "news_analysis"}}

data: {"type": "status", "message": "Đang phân tích tin tức...", "progress": 30}

data: {"type": "section_start", "section": "news_analysis", "title": "Phân Tích Tin Tức"}

data: {"type": "content", "section": "news_analysis", "text": "Tin tức gần đây tích cực..."}

data: {"type": "section_end", "section": "news_analysis"}

data: {"type": "complete", "message": "Phân tích tin tức hoàn tất!", "progress": 100}
```

**Features:**
- Sử dụng Redis cache với TTL 2 giờ (tin tức thay đổi thường xuyên)
- Phân tích tin tức và sentiment thị trường
- Cache key: `news_analysis:{ticker}:{look_back_days}`

#### 9. Phân tích giao dịch tự doanh (Streaming)
```http
POST /api/proprietary-trading-analysis/stream
```

**Headers:**
- `Accept: text/event-stream` (để nhận streaming response)
- Session cookie (automatic)

**Request Body:**
```json
{
  "ticker": "VCB"
}
```

**Response (Server-Sent Events):**
```
data: {"type": "metadata", "data": {"ticker": "VCB", "analysis_type": "proprietary_trading_analysis"}}

data: {"type": "status", "message": "Đang phân tích giao dịch tự doanh...", "progress": 45}

data: {"type": "section_start", "section": "proprietary_trading_analysis", "title": "Phân Tích Giao Dịch Tự Doanh"}

data: {"type": "content", "section": "proprietary_trading_analysis", "text": "Khối tự doanh đang có xu hướng mua ròng..."}

data: {"type": "section_end", "section": "proprietary_trading_analysis"}

data: {"type": "complete", "message": "Phân tích giao dịch tự doanh hoàn tất!", "progress": 100}
```

**Features:**
- Sử dụng Redis cache với TTL 4 giờ
- Phân tích giao dịch tự doanh từ dữ liệu CafeF
- Cache key: `proprietary_trading:{ticker}`

#### 10. Phân tích giao dịch khối ngoại (Streaming)
```http
POST /api/foreign-trading-analysis/stream
```

**Headers:**
- `Accept: text/event-stream` (để nhận streaming response)
- Session cookie (automatic)

**Request Body:**
```json
{
  "ticker": "VCB"
}
```

**Response (Server-Sent Events):**
```
data: {"type": "metadata", "data": {"ticker": "VCB", "analysis_type": "foreign_trading_analysis"}}

data: {"type": "status", "message": "Đang phân tích giao dịch khối ngoại...", "progress": 60}

data: {"type": "section_start", "section": "foreign_trading_analysis", "title": "Phân Tích Giao Dịch Khối Ngoại"}

data: {"type": "content", "section": "foreign_trading_analysis", "text": "Khối ngoại đang có xu hướng bán ròng..."}

data: {"type": "section_end", "section": "foreign_trading_analysis"}

data: {"type": "complete", "message": "Phân tích giao dịch khối ngoại hoàn tất!", "progress": 100}
```

**Features:**
- Sử dụng Redis cache với TTL 4 giờ
- Phân tích giao dịch khối ngoại từ dữ liệu CafeF
- Cache key: `foreign_trading:{ticker}`

#### 11. Phân tích giao dịch cổ đông nội bộ (Streaming)
```http
POST /api/shareholder-trading-analysis/stream
```

**Headers:**
- `Accept: text/event-stream` (để nhận streaming response)
- Session cookie (automatic)

**Request Body:**
```json
{
  "ticker": "VCB"
}
```

**Response (Server-Sent Events):**
```
data: {"type": "metadata", "data": {"ticker": "VCB", "analysis_type": "shareholder_trading_analysis"}}

data: {"type": "status", "message": "Đang phân tích giao dịch cổ đông...", "progress": 75}

data: {"type": "section_start", "section": "shareholder_trading_analysis", "title": "Phân Tích Giao Dịch Cổ Đông Nội Bộ"}

data: {"type": "content", "section": "shareholder_trading_analysis", "text": "Các cổ đông nội bộ đang có kế hoạch mua thêm..."}

data: {"type": "section_end", "section": "shareholder_trading_analysis"}

data: {"type": "complete", "message": "Phân tích giao dịch cổ đông hoàn tất!", "progress": 100}
```

**Features:**
- Sử dụng Redis cache với TTL 8 giờ
- Phân tích giao dịch cổ đông nội bộ từ dữ liệu CafeF
- Cache key: `shareholder_trading:{ticker}`

#### 12. Phân tích khớp lệnh trong phiên (Streaming)
```http
POST /api/intraday_match_analysis
```

**Headers:**
- `Accept: text/event-stream` (để nhận streaming response)
- Session cookie (automatic)

**Query Parameters:**
- `symbol` (string, required): Mã cổ phiếu
- `date` (string, required): Ngày phân tích (YYYY-MM-DD hoặc YYYYMMDD)

**Example:**
```http
POST /api/intraday_match_analysis?symbol=VCB&date=2024-01-15
```

**Response (Server-Sent Events):**
```
data: {"type": "metadata", "data": {"ticker": "VCB", "date": "2024-01-15"}}

data: {"type": "status", "message": "Đang tạo phân tích khớp lệnh trong phiên..", "progress": 0}

data: {"type": "section_start", "section": "intraday_analysis", "title": "Phân Tích Khớp Lệnh Trong Phiên"}

data: {"type": "status", "message": "Đang tải dữ liệu khớp lệnh trong phiên...", "progress": 10}

data: {"type": "content", "section": "intraday_analysis", "text": "Phân tích chi tiết về giá khớp lệnh..."}

data: {"type": "section_end", "section": "intraday_analysis"}

data: {"type": "complete", "message": "Phân tích khớp lệnh hoàn tất", "progress": 100}
```

**Features:**
- Sử dụng Redis cache với TTL 12 giờ
- Phân tích dữ liệu khớp lệnh theo thời gian thực
- Đánh giá lực cầu/cung trong phiên
- Phân tích xu hướng giá và thanh khoản
- Đưa ra nhận định xu hướng ngắn hạn
- Cache key: `intraday_analysis:{ticker}:{date}`

#### 9. Gửi cảnh báo
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
  "description": "Hệ thống quản lý rủi ro tài chính với AI",
  "features": [
    "Stock Analysis with AI",
    "Portfolio Optimization", 
    "News Analysis",
    "Technical Analysis",
    "Real-time Streaming",
    "Redis Caching"
  ],
  "endpoints": {
    "financial_analysis": [
      "/api/stock_data",
      "/api/technical_signals", 
      "/api/news",
      "/api/technical-analysis/stream",
      "/api/news-analysis/stream",
      "/api/proprietary-trading-analysis/stream",
      "/api/foreign-trading-analysis/stream",
      "/api/shareholder-trading-analysis/stream",
      "/api/intraday_match_analysis"
    ],
    "user_management": [
      "/api/auth/*",
      "/api/wallet/*", 
      "/api/packages/*"
    ],
    "insights_history": [
      "/api/insights-history",
      "/api/insights-history/{insight_id}",
      "/api/insights-history/stats"
    ]
  },
  "docs": "/docs",
  "redoc": "/redoc"
}
```

#### 3. System health check
```http
GET /api/system/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "3.0.0",
  "environment": "production",
  "database": "connected",
  "redis": "connected",
  "services": {
    "supabase": "healthy",
    "redis_cache": "healthy",
    "performance_monitor": "active"
  }
}
```

#### 4. System metrics
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
    "requests_per_minute": 10.5,
    "performance_stats": {
      "slow_requests": 5,
      "cache_hit_rate": 0.85,
      "memory_usage": "45%"
    }
  }
}
```

#### 5. System status
```http
GET /api/system/status
```

**Response:**
```json
{
  "success": true,
  "status": {
    "database": "connected",
    "redis": "connected", 
    "performance": {
      "uptime": 86400,
      "total_requests": 1000,
      "average_response_time": 0.25
    },
    "services": {
      "auth_manager": "active",
      "wallet_manager": "active", 
      "cache_manager": "active",
      "notification_manager": "active"
    },
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

---

## 💾 Cache Management

### Cache Endpoints

#### 1. Lấy trạng thái cache
```http
GET /api/cache/status
```

**Response:**
```json
{
  "status": "active",
  "redis_connected": true,
  "total_keys": 1250,
  "memory_usage": "45MB",
  "hit_rate": 0.85,
  "cache_types": {
    "stock_data": 450,
    "technical_signals": 320,
    "news_analysis": 280, 
    "ai_insights": 200
  }
}
```

#### 2. Làm mới cache
```http
POST /api/cache/refresh
```

**Headers:** Session cookie (automatic) - Admin required

**Response:**
```json
{
  "message": "Cache refresh initiated",
  "refreshed_keys": 1250,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### 3. Xóa cache
```http
DELETE /api/cache/clear
```

**Headers:** Session cookie (automatic) - Admin required

**Response:**
```json
{
  "message": "Cache cleared successfully",
  "cleared_keys": 1250
}
```

#### 4. Lấy danh sách symbols trong cache
```http
GET /api/cache/symbols
```

**Response:**
```json
{
  "cached_symbols": ["VCB", "BID", "CTG", "TCB", "MBB"],
  "total_symbols": 5,
  "cache_types": {
    "stock_data": ["VCB", "BID"],
    "technical_signals": ["VCB", "CTG"], 
    "news_analysis": ["VCB", "BID", "TCB"]
  }
}
```

#### 5. Kiểm tra cache cho symbol cụ thể
```http
GET /api/cache/symbol/{symbol}
```

**Response:**
```json
{
  "symbol": "VCB",
  "cached_data": {
    "stock_data": {
      "exists": true,
      "ttl": 1200,
      "last_updated": "2024-01-01T10:00:00Z"
    },
    "technical_signals": {
      "exists": true, 
      "ttl": 2400,
      "last_updated": "2024-01-01T09:30:00Z"
    },
    "news_analysis": {
      "exists": false
    }
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
- `X-API-Version` - API version (3.0.0)
- `Cache-Control` - Caching policy
- `X-Content-Type-Options` - Security header
- `X-Frame-Options` - Security header
- `X-XSS-Protection` - Security header
- `Strict-Transport-Security` - Security header
- `Referrer-Policy` - Security header

---

## 🆓 CafeF Free Data APIs

Các API miễn phí từ CafeF để lấy dữ liệu thị trường chứng khoán Việt Nam. **Không cần authentication và không tính phí sử dụng.**

### Financial Data Endpoints

#### 1. Lấy dữ liệu giao dịch cổ đông
```http
POST /api/cafef/shareholder-data
```

**Request Body:**
```json
{
  "symbol": "VCB",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "page_index": 1,
  "page_size": 14
}
```

**Response:**
```json
{
  "success": true,
  "symbol": "VCB",
  "data": [
    {
      "Stock": "VCB",
      "TransactionMan": "Nguyễn Văn A",
      "TransactionManPosition": "Chủ tịch HĐQT",
      "VolumeBeforeTransaction": 1000000,
      "PlanBuyVolume": 50000,
      "PlanSellVolume": 0,
      "RealBuyVolume": 50000,
      "RealSellVolume": 0,
      "VolumeAfterTransaction": 1050000,
      "TyLeSoHuu": 2.5
    }
  ],
  "page_index": 1,
  "page_size": 14
}
```

#### 2. Lấy lịch sử giá cổ phiếu
```http
POST /api/cafef/price-history
```

**Request Body:**
```json
{
  "symbol": "VCB",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "page_index": 1,
  "page_size": 14
}
```

#### 3. Lấy dữ liệu giao dịch khối ngoại
```http
POST /api/cafef/foreign-trading
```

**Request Body:**
```json
{
  "symbol": "VCB",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "page_index": 1,
  "page_size": 14
}
```

**Response:**
```json
{
  "success": true,
  "symbol": "VCB",
  "data": [
    {
      "Ngay": "2024-01-15",
      "KLGDRong": 125000,
      "GTDGRong": 12.5,
      "ThayDoi": 1.2,
      "KLMua": 200000,
      "GtMua": 20.0,
      "KLBan": 75000,
      "GtBan": 7.5,
      "RoomConLai": 15.5,
      "DangSoHuu": 4.5
    }
  ]
}
```

#### 4. Lấy dữ liệu giao dịch tự doanh
```http
POST /api/cafef/proprietary-trading
```

**Request Body:**
```json
{
  "symbol": "VCB",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31", 
  "page_index": 1,
  "page_size": 14
}
```

#### 5. Lấy giá khớp lệnh theo ngày
```http
POST /api/cafef/match-price
```

**Request Body:**
```json
{
  "symbol": "VCB",
  "date": "2024-01-15"
}
```

**Response:**
```json
{
  "success": true,
  "symbol": "VCB",
  "date": "2024-01-15",
  "data": {
    "match_data": [
      {
        "time": "09:00:00",
        "price": 95500,
        "volume": 1250,
        "change": 500
      }
    ]
  }
}
```

#### 6. Lấy giá realtime
```http
GET /api/cafef/realtime-price/{symbol}
```

**Example:**
```http
GET /api/cafef/realtime-price/VCB
```

**Response:**
```json
{
  "success": true,
  "symbol": "VCB",
  "data": {
    "price": 95500,
    "change": 500,
    "change_percent": 0.53,
    "volume": 1250000,
    "timestamp": "2024-01-15T14:30:00Z"
  }
}
```

### Company Information Endpoints

**Note:** Các API 7-11 trả về file .aspx với content type `text/html` và header `Content-Disposition: attachment`.

#### 7. Lấy thông tin công ty
```http
GET /api/cafef/company-info/{symbol}
```

**Response:** File .aspx với thông tin công ty (HTML content)

**Headers:**
```
Content-Type: text/html
Content-Disposition: attachment; filename=VCB_company_info.aspx
```

#### 8. Lấy danh sách ban lãnh đạo
```http
GET /api/cafef/leadership/{symbol}
```

**Response:** File .aspx với danh sách ban lãnh đạo (HTML content)

**Headers:**
```
Content-Type: text/html
Content-Disposition: attachment; filename=VCB_leadership.aspx
```

#### 9. Lấy danh sách công ty con
```http
GET /api/cafef/subsidiaries/{symbol}
```

**Response:** File .aspx với danh sách công ty con (HTML content)

**Headers:**
```
Content-Type: text/html
Content-Disposition: attachment; filename=VCB_subsidiaries.aspx
```

#### 10. Lấy báo cáo tài chính
```http
GET /api/cafef/financial-reports/{symbol}
```

**Response:** File .aspx với báo cáo tài chính (HTML content)

**Headers:**
```
Content-Type: text/html
Content-Disposition: attachment; filename=VCB_financial_reports.aspx
```

#### 11. Lấy hồ sơ công ty
```http
POST /api/cafef/company-profile
```

**Request Body:**
```json
{
  "symbol": "VCB",
  "type_id": 1,
  "page_index": 0,
  "page_size": 4
}
```

**Response:** File .aspx với hồ sơ công ty (HTML content)

**Headers:**
```
Content-Type: text/html
Content-Disposition: attachment; filename=VCB_company_profile.aspx
```

### Additional Data Endpoints

#### 12. Lấy dữ liệu tài chính
```http
GET /api/cafef/finance-data/{symbol}
```

**Response:**
```json
{
  "success": true,
  "symbol": "VCB",
  "data": {
        {
        "Symbol": "VIC",
        "Year": 2024,
        "EPS": 3.04,
        "BV": 35.93,
        "PE": 13.49,
        "ROA": 1.42,
        "ROE": 7.74,
        "ROS": 6.29,
        "GOS": 14.44,
        "DAR": 81.61,
        "IsCurrent": false,
        "LastUpdate": "\/Date(1744170898268)\/"
    }, {
        "Year": 2023,
        "Symbol": "VIC",
        "EPS": 0.56,
        "BV": 29.75,
        "PE": 79.64,
        "ROA": 0.32,
        "ROE": 1.46,
        "ROS": 1.34,
        "GOS": 14.56,
        "DAR": 77.8,
        "IsCurrent": false,
        "LastUpdate": "\/Date(1712023636848)\/"
    }
  }
}
```

#### 13. Lấy chỉ số thế giới
```http
GET /api/cafef/global-indices
```

**Response:**
```json
{
  "success": true,
  "data": [
    [{"id":"51","index":"SSE Composite Index","last":3865.26,"high":3876.24,"low":3850.37,"change":-10.91,"changePercent":-0.28,"lastUpdate":"2025-10-20 00:00:00","district":1},{"id":"31","index":"SZSE Component B","last":8895.67,"high":8933.77,"low":8887.98,"change":-31.18,"changePercent":-0.35,"lastUpdate":"2025-10-20 00:00:00","district":1},{"id":"29","index":"FTSE MIB Index","last":42443.69,"high":42496.1,"low":42095.11,"change":321.23,"changePercent":0.76,"lastUpdate":"2025-10-20 00:00:00","district":2},{"id":"22","index":"PSI","last":8325.18,"high":8350.58,"low":8268.21,"change":49.55,"changePercent":0.6,"lastUpdate":"2025-10-20 00:00:00","district":2},{"id":"52","index":"VinFast Auto Ltd.","last":3.27,"high":3.29,"low":3.26,"change":0,"changePercent":0.11,"lastUpdate":"2025-10-20 00:00:00","district":3}]
  ]
}
```

**Features của CafeF APIs:**
- **Miễn phí hoàn toàn** - Không cần authentication
- **Không tính phí** - Không trừ coins hoặc credits
- **Dữ liệu thời gian thực** - Cập nhật liên tục từ CafeF
- **Đa dạng dữ liệu** - Từ giá cổ phiếu đến thông tin công ty
- **Format linh hoạt** - JSON và file .aspx tùy loại dữ liệu

---

## 📝 Notes

### Rate Limiting
- Không có rate limiting cụ thể được implement
- Khuyến nghị implement rate limiting trong production
- Performance monitoring được áp dụng để theo dõi request times
- Requests > 2 giây được log như slow requests

### Caching Strategy
- **Redis Cache** được sử dụng cho các API chính:
  - Stock data: 30 phút TTL
  - Technical signals: 1 giờ TTL
  - News analysis: 1 giờ TTL
  - AI insights: 6 giờ TTL (full analysis với multiple phases)
- Cache keys có format: `service_type:symbol:parameters_hash`
- Streaming APIs kiểm tra cache trước khi thực hiện phân tích mới

### Pagination
- Hầu hết endpoints hỗ trợ `limit` và `offset`
- Default limit thường là 50
- Maximum limit khuyến nghị: 100

### Service Tracking
- Các API financial analysis được track sử dụng dịch vụ
- Cần có gói dịch vụ hoặc coins để sử dụng
- Các API có Redis cache để tăng hiệu suất:
  - `/api/stock_data` (30 phút)
  - `/api/technical_signals` (1 giờ)
  - `/api/news` (1 giờ)
  - `/api/technical-analysis/stream` (6 giờ)
  - `/api/news-analysis/stream` (2 giờ)
  - `/api/proprietary-trading-analysis/stream` (4 giờ)
  - `/api/foreign-trading-analysis/stream` (4 giờ)
  - `/api/shareholder-trading-analysis/stream` (8 giờ)
  - `/api/intraday_match_analysis` (12 giờ)

### Insights History
- Tất cả phân tích từ streaming APIs tự động được lưu vào Supabase
- Giới hạn 10 phân tích gần nhất cho mỗi loại phân tích (`analysis_type`)
- Database trigger tự động xóa phân tích cũ nhất khi vượt quá giới hạn
- Row Level Security (RLS) đảm bảo user chỉ truy cập phân tích của mình
- Metadata được lưu linh hoạt theo từng loại phân tích
- Hỗ trợ filter, pagination, và thống kê chi tiết

### Authentication Levels
1. **Public**: Không cần authentication
2. **User**: Cần session cookie
3. **Admin**: Cần session cookie với role admin

---

## 🔗 Interactive Documentation

- **Swagger UI:** `/docs`
- **ReDoc:** `/redoc`

Sử dụng Swagger UI để test các API endpoints trực tiếp từ browser.
