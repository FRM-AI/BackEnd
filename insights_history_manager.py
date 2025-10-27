"""
Insights History Manager
Module quản lý lịch sử phân tích insights của người dùng
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel
from supabase_config import get_supabase_client
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Pydantic Models
class InsightHistoryCreate(BaseModel):
    ticker: str
    asset_type: str = "stock"
    analysis_type: str
    content: str
    metadata: Optional[Dict[str, Any]] = {}

class InsightHistory(BaseModel):
    id: str
    user_id: str
    ticker: str
    asset_type: str
    analysis_type: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class InsightsHistoryManager:
    """Manager for handling insights history operations"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.max_insights_per_type = 10
    
    async def save_insight(
        self, 
        user_id: str, 
        insight_data: InsightHistoryCreate
    ) -> InsightHistory:
        """
        Lưu phân tích mới vào lịch sử
        Tự động xóa phân tích cũ nhất nếu vượt quá 10 (được xử lý bởi trigger)
        """
        try:
            # Chuẩn bị dữ liệu
            insert_data = {
                "user_id": user_id,
                "ticker": insight_data.ticker.upper(),
                "asset_type": insight_data.asset_type,
                "analysis_type": insight_data.analysis_type,
                "content": insight_data.content,
                "metadata": insight_data.metadata or {}
            }
            
            # Thêm vào database (trigger sẽ tự động cleanup)
            result = self.supabase.table('insights_history') \
                .insert(insert_data) \
                .execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=500, 
                    detail="Không thể lưu lịch sử phân tích"
                )
            
            logger.info(
                f"Saved insight for user {user_id}: "
                f"{insight_data.analysis_type} - {insight_data.ticker}"
            )
            
            return InsightHistory(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error saving insight history: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi lưu lịch sử: {str(e)}"
            )
    
    async def get_user_insights(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        analysis_type: Optional[str] = None,
        ticker: Optional[str] = None
    ) -> List[InsightHistory]:
        """
        Lấy danh sách lịch sử phân tích của user
        """
        try:
            query = self.supabase.table('insights_history') \
                .select('*') \
                .eq('user_id', user_id) \
                .order('created_at', desc=True)
            
            # Filter by analysis_type if provided
            if analysis_type:
                query = query.eq('analysis_type', analysis_type)
            
            # Filter by ticker if provided
            if ticker:
                query = query.eq('ticker', ticker.upper())
            
            # Apply pagination
            query = query.range(offset, offset + limit - 1)
            
            result = query.execute()
            
            insights = [InsightHistory(**item) for item in result.data]
            
            logger.info(
                f"Retrieved {len(insights)} insights for user {user_id}"
            )
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting user insights: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi lấy lịch sử: {str(e)}"
            )
    
    async def get_insight_by_id(
        self,
        user_id: str,
        insight_id: str
    ) -> Optional[InsightHistory]:
        """
        Lấy chi tiết một phân tích theo ID
        """
        try:
            result = self.supabase.table('insights_history') \
                .select('*') \
                .eq('id', insight_id) \
                .eq('user_id', user_id) \
                .execute()
            
            if not result.data:
                return None
            
            return InsightHistory(**result.data[0])
            
        except Exception as e:
            logger.error(f"Error getting insight by id: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi lấy chi tiết phân tích: {str(e)}"
            )
    
    async def delete_insight(
        self,
        user_id: str,
        insight_id: str
    ) -> Dict[str, str]:
        """
        Xóa một phân tích
        """
        try:
            result = self.supabase.table('insights_history') \
                .delete() \
                .eq('id', insight_id) \
                .eq('user_id', user_id) \
                .execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=404,
                    detail="Không tìm thấy phân tích"
                )
            
            logger.info(f"Deleted insight {insight_id} for user {user_id}")
            
            return {"message": "Đã xóa phân tích thành công"}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting insight: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi xóa phân tích: {str(e)}"
            )
    
    async def delete_all_user_insights(
        self,
        user_id: str
    ) -> Dict[str, str]:
        """
        Xóa tất cả lịch sử phân tích của user
        """
        try:
            result = self.supabase.table('insights_history') \
                .delete() \
                .eq('user_id', user_id) \
                .execute()
            
            count = len(result.data) if result.data else 0
            
            logger.info(f"Deleted all {count} insights for user {user_id}")
            
            return {
                "message": f"Đã xóa {count} phân tích",
                "count": count
            }
            
        except Exception as e:
            logger.error(f"Error deleting all insights: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi xóa lịch sử: {str(e)}"
            )
    
    async def get_insights_stats(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Lấy thống kê lịch sử phân tích của user
        """
        try:
            # Get all insights for stats
            result = self.supabase.table('insights_history') \
                .select('analysis_type, ticker, created_at') \
                .eq('user_id', user_id) \
                .execute()
            
            insights = result.data
            
            # Calculate statistics
            total = len(insights)
            
            # Count by analysis type
            type_counts = {}
            for insight in insights:
                analysis_type = insight.get('analysis_type', 'unknown')
                type_counts[analysis_type] = type_counts.get(analysis_type, 0) + 1
            
            # Count by ticker
            ticker_counts = {}
            for insight in insights:
                ticker = insight.get('ticker', 'unknown')
                ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
            
            # Get most analyzed ticker
            most_analyzed_ticker = max(
                ticker_counts.items(), 
                key=lambda x: x[1]
            ) if ticker_counts else ("N/A", 0)
            
            # Get most used analysis type
            most_used_type = max(
                type_counts.items(),
                key=lambda x: x[1]
            ) if type_counts else ("N/A", 0)
            
            return {
                "total_insights": total,
                "by_analysis_type": type_counts,
                "by_ticker": ticker_counts,
                "most_analyzed_ticker": {
                    "ticker": most_analyzed_ticker[0],
                    "count": most_analyzed_ticker[1]
                },
                "most_used_analysis": {
                    "type": most_used_type[0],
                    "count": most_used_type[1]
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting insights stats: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi lấy thống kê: {str(e)}"
            )
    
    async def check_duplicate(
        self,
        user_id: str,
        ticker: str,
        analysis_type: str,
        minutes: int = 5
    ) -> bool:
        """
        Kiểm tra xem có phân tích trùng lặp trong X phút gần đây không
        Giúp tránh spam và tiết kiệm tài nguyên
        """
        try:
            from datetime import timedelta
            
            # Calculate time threshold
            time_threshold = datetime.now() - timedelta(minutes=minutes)
            
            result = self.supabase.table('insights_history') \
                .select('id') \
                .eq('user_id', user_id) \
                .eq('ticker', ticker.upper()) \
                .eq('analysis_type', analysis_type) \
                .gte('created_at', time_threshold.isoformat()) \
                .execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return False

# Global instance
insights_history_manager = InsightsHistoryManager()
