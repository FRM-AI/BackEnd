# 📊 Insights History Setup Guide

## Giới thiệu

Hệ thống Insights History cho phép lưu trữ lịch sử phân tích của người dùng với các tính năng:
- ✅ Tự động lưu phân tích từ streaming APIs
- ✅ Giới hạn 10 phân tích gần nhất cho mỗi loại
- ✅ Tự động xóa phân tích cũ (database trigger)
- ✅ Row Level Security (RLS) cho bảo mật
- ✅ API đầy đủ cho CRUD operations

---

## 🚀 Cài đặt

### Bước 1: Chạy Database Migration

Truy cập Supabase Dashboard và chạy file migration:

```bash
# File migration location
BackEnd/insights_history_migration.sql
```

**Hoặc sử dụng Supabase CLI:**

```bash
cd BackEnd
supabase db push
```

**Hoặc copy nội dung file và chạy trong SQL Editor:**

1. Mở Supabase Dashboard
2. Vào **SQL Editor**
3. Copy toàn bộ nội dung `insights_history_migration.sql`
4. Paste và click **Run**

### Bước 2: Verify Migration

Kiểm tra xem bảng đã được tạo thành công:

```sql
-- Kiểm tra bảng
SELECT * FROM insights_history LIMIT 1;

-- Kiểm tra indexes
SELECT indexname FROM pg_indexes WHERE tablename = 'insights_history';

-- Kiểm tra triggers
SELECT trigger_name FROM information_schema.triggers 
WHERE event_object_table = 'insights_history';

-- Kiểm tra RLS policies
SELECT policyname, cmd FROM pg_policies 
WHERE tablename = 'insights_history';
```

### Bước 3: Test APIs

Restart FastAPI server và test các endpoints:

```bash
# Restart server
cd BackEnd
python app_fastapi.py
```

**Test endpoints:**

```bash
# 1. Lấy lịch sử (cần đăng nhập trước)
curl -X GET "http://localhost:8000/api/insights-history" \
  -H "Cookie: session_id=YOUR_SESSION_ID"

# 2. Lấy thống kê
curl -X GET "http://localhost:8000/api/insights-history/stats" \
  -H "Cookie: session_id=YOUR_SESSION_ID"

# 3. Thực hiện một phân tích để tự động lưu
curl -X POST "http://localhost:8000/api/technical-analysis/stream" \
  -H "Content-Type: application/json" \
  -H "Cookie: session_id=YOUR_SESSION_ID" \
  -d '{
    "ticker": "VCB",
    "asset_type": "stock",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'

# 4. Kiểm tra lại lịch sử
curl -X GET "http://localhost:8000/api/insights-history" \
  -H "Cookie: session_id=YOUR_SESSION_ID"
```

---

## 🏗️ Kiến trúc

### Database Schema

```
insights_history
├── id (UUID, Primary Key)
├── user_id (UUID, Foreign Key -> users)
├── ticker (VARCHAR(20))
├── asset_type (VARCHAR(20))
├── analysis_type (VARCHAR(50))
├── content (TEXT)
├── metadata (JSONB)
├── created_at (TIMESTAMP WITH TIME ZONE)
└── updated_at (TIMESTAMP WITH TIME ZONE)
```

### Indexes

1. `idx_insights_history_user_id` - Tìm kiếm theo user
2. `idx_insights_history_ticker` - Tìm kiếm theo ticker
3. `idx_insights_history_analysis_type` - Tìm kiếm theo loại phân tích
4. `idx_insights_history_created_at` - Sắp xếp theo thời gian
5. `idx_insights_history_user_created` - Composite index cho user + time
6. `idx_insights_history_user_ticker_type` - Composite index cho filter phức tạp

### Triggers

1. **update_insights_history_updated_at**: Tự động cập nhật `updated_at` khi record được update
2. **cleanup_old_insights**: Tự động xóa phân tích cũ nhất khi vượt quá 10 records cho mỗi `analysis_type`

### RLS Policies

1. **Users can view their own insights history** - SELECT
2. **Users can insert their own insights history** - INSERT
3. **Users can delete their own insights history** - DELETE
4. **Users can update their own insights history** - UPDATE

---

## 📝 Cách sử dụng

### 1. Tự động lưu từ Streaming APIs

Khi user thực hiện phân tích qua các streaming APIs, hệ thống tự động lưu:

```python
# Trong app_fastapi.py
if current_user and analysis_content:
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
```

### 2. Lấy lịch sử phân tích

```python
# Frontend/Client code
const response = await fetch('/api/insights-history?analysis_type=technical_analysis&ticker=VCB', {
  credentials: 'include' // Để gửi cookie
});
const insights = await response.json();
```

### 3. Xem thống kê

```python
const response = await fetch('/api/insights-history/stats', {
  credentials: 'include'
});
const stats = await response.json();
console.log(`Tổng số phân tích: ${stats.total_insights}`);
console.log(`Cổ phiếu được phân tích nhiều nhất: ${stats.most_analyzed_ticker.ticker}`);
```

---

## 🔍 Các loại phân tích được lưu

| Analysis Type | Streaming API | Cache TTL | Auto Save |
|---------------|---------------|-----------|-----------|
| `technical_analysis` | `/api/technical-analysis/stream` | 6 giờ | ✅ |
| `news_analysis` | `/api/news-analysis/stream` | 2 giờ | ✅ |
| `proprietary_trading_analysis` | `/api/proprietary-trading-analysis/stream` | 4 giờ | ✅ |
| `foreign_trading_analysis` | `/api/foreign-trading-analysis/stream` | 4 giờ | ✅ |
| `shareholder_trading_analysis` | `/api/shareholder-trading-analysis/stream` | 8 giờ | ✅ |
| `intraday_match_analysis` | `/api/intraday_match_analysis` | 12 giờ | ✅ |

---

## 🛠️ Troubleshooting

### Lỗi: "relation insights_history does not exist"

**Giải pháp:** Chạy lại migration SQL trong Supabase Dashboard

```sql
-- Copy toàn bộ nội dung từ insights_history_migration.sql và run
```

### Lỗi: "permission denied for table insights_history"

**Giải pháp:** Kiểm tra RLS policies và grants

```sql
-- Verify grants
SELECT grantee, privilege_type 
FROM information_schema.role_table_grants 
WHERE table_name='insights_history';

-- Verify RLS is enabled
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE tablename='insights_history';
```

### Phân tích không được lưu tự động

**Giải pháp:** 
1. Kiểm tra user đã đăng nhập chưa (`current_user` phải tồn tại)
2. Kiểm tra log để xem lỗi: `grep "Failed to save.*to history" frm_ai.log`
3. Verify `insights_history_manager` được import trong `app_fastapi.py`

### Không thể xem lịch sử phân tích

**Giải pháp:**
1. Kiểm tra session cookie có hợp lệ không
2. Verify RLS policies: `SELECT * FROM pg_policies WHERE tablename='insights_history'`
3. Test với admin user để xem có phải lỗi permissions

---

## 📚 Tài liệu tham khảo

- **API Documentation:** `BackEnd/API_DOCUMENTATION.md` (Section: Insights History Management)
- **Migration SQL:** `BackEnd/insights_history_migration.sql`
- **Manager Module:** `BackEnd/insights_history_manager.py`
- **Integration:** `BackEnd/app_fastapi.py` (Search: "insights_history")

---

## ✅ Checklist

- [ ] Chạy migration SQL thành công
- [ ] Verify bảng, indexes, triggers đã được tạo
- [ ] Test API GET `/api/insights-history`
- [ ] Test API GET `/api/insights-history/stats`
- [ ] Thực hiện một phân tích streaming
- [ ] Verify phân tích được lưu tự động
- [ ] Test xóa phân tích
- [ ] Test giới hạn 10 phân tích (tạo 11+ phân tích cùng loại)
- [ ] Verify RLS policies hoạt động đúng

---

## 🎉 Hoàn tất!

Hệ thống Insights History đã sẵn sàng sử dụng. User có thể:
- ✅ Xem lại các phân tích đã thực hiện
- ✅ Lọc theo ticker và loại phân tích
- ✅ Xem thống kê tổng quan
- ✅ Xóa phân tích không cần thiết
- ✅ Tự động giới hạn 10 phân tích gần nhất
