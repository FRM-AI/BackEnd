"""
White Label System Management
Hệ thống quản lý white label và đa thương hiệu
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from fastapi import HTTPException
from supabase_config import get_supabase_client
import logging

logger = logging.getLogger(__name__)

# Pydantic Models
class WhiteLabelConfig(BaseModel):
    id: str
    domain: str
    brand_name: str
    logo_url: Optional[str] = None
    primary_color: str = "#1e40af"
    secondary_color: str = "#3b82f6"
    accent_color: str = "#10b981"
    theme_config: Dict[str, Any] = {}
    features_enabled: List[str] = []
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None
    contact_info: Dict[str, str] = {}
    social_links: Dict[str, str] = {}
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

class WhiteLabelCreate(BaseModel):
    domain: str = Field(..., min_length=1)
    brand_name: str = Field(..., min_length=1)
    logo_url: Optional[str] = None
    primary_color: str = "#1e40af"
    secondary_color: str = "#3b82f6"
    accent_color: str = "#10b981"
    theme_config: Dict[str, Any] = {}
    features_enabled: List[str] = []
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None
    contact_info: Dict[str, str] = {}
    social_links: Dict[str, str] = {}

class WhiteLabelUpdate(BaseModel):
    brand_name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    theme_config: Optional[Dict[str, Any]] = None
    features_enabled: Optional[List[str]] = None
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None
    contact_info: Optional[Dict[str, str]] = None
    social_links: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None

class WhiteLabelManager:
    def __init__(self):
        self.supabase = get_supabase_client()
        
        # Default features that can be enabled/disabled
        self.AVAILABLE_FEATURES = [
            'stock_analysis',
            'technical_analysis',
            'portfolio_optimization',
            'news_analysis',
            'fundamental_scoring',
            'ai_insights',
            'alerts',
            'social_features',
            'advanced_charts',
            'real_time_data',
            'mobile_app',
            'api_access',
            'white_label_branding'
        ]
        
        # Default theme configuration
        self.DEFAULT_THEME = {
            'typography': {
                'primary_font': 'Inter',
                'secondary_font': 'Roboto',
                'font_sizes': {
                    'xs': '12px',
                    'sm': '14px',
                    'base': '16px',
                    'lg': '18px',
                    'xl': '20px',
                    '2xl': '24px',
                    '3xl': '30px',
                    '4xl': '36px'
                }
            },
            'layout': {
                'sidebar_width': '250px',
                'header_height': '64px',
                'border_radius': '8px',
                'spacing_unit': '8px'
            },
            'components': {
                'button_style': 'rounded',
                'input_style': 'outlined',
                'card_shadow': 'medium'
            }
        }
    
    async def create_white_label(self, config_data: WhiteLabelCreate) -> WhiteLabelConfig:
        """Create new white label configuration"""
        try:
            # Check if domain already exists
            existing = self.supabase.table('white_label_configs')\
                .select("domain")\
                .eq('domain', config_data.domain)\
                .execute()
            
            if existing.data:
                raise HTTPException(status_code=400, detail="Domain đã được sử dụng")
            
            # Merge with default theme
            theme_config = {**self.DEFAULT_THEME, **config_data.theme_config}
            
            # Prepare data
            insert_data = {
                **config_data.dict(),
                'theme_config': theme_config,
                'is_active': True
            }
            
            result = self.supabase.table('white_label_configs').insert(insert_data).execute()
            
            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể tạo cấu hình white label")
            
            return WhiteLabelConfig(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Create white label error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi tạo cấu hình white label")
    
    async def get_white_label_by_domain(self, domain: str) -> Optional[WhiteLabelConfig]:
        """Get white label configuration by domain"""
        try:
            result = self.supabase.table('white_label_configs')\
                .select("*")\
                .eq('domain', domain)\
                .eq('is_active', True)\
                .execute()
            
            if result.data:
                return WhiteLabelConfig(**result.data[0])
            
            return None
            
        except Exception as e:
            logger.error(f"Get white label by domain error: {e}")
            return None
    
    async def get_white_label(self, config_id: str) -> WhiteLabelConfig:
        """Get white label configuration by ID"""
        try:
            result = self.supabase.table('white_label_configs')\
                .select("*")\
                .eq('id', config_id)\
                .execute()
            
            if not result.data:
                raise HTTPException(status_code=404, detail="Cấu hình white label không tồn tại")
            
            return WhiteLabelConfig(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get white label error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy cấu hình white label")
    
    async def update_white_label(self, config_id: str, update_data: WhiteLabelUpdate) -> WhiteLabelConfig:
        """Update white label configuration"""
        try:
            # Check if config exists
            await self.get_white_label(config_id)
            
            # Prepare update data
            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
            
            if not update_dict:
                raise HTTPException(status_code=400, detail="Không có dữ liệu để cập nhật")
            
            result = self.supabase.table('white_label_configs')\
                .update(update_dict)\
                .eq('id', config_id)\
                .execute()
            
            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể cập nhật cấu hình")
            
            return WhiteLabelConfig(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Update white label error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi cập nhật cấu hình white label")
    
    async def list_white_labels(self, include_inactive: bool = False) -> List[WhiteLabelConfig]:
        """List all white label configurations"""
        try:
            query = self.supabase.table('white_label_configs').select("*")
            
            if not include_inactive:
                query = query.eq('is_active', True)
            
            result = query.order('created_at', desc=True).execute()
            
            return [WhiteLabelConfig(**config) for config in result.data]
            
        except Exception as e:
            logger.error(f"List white labels error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy danh sách cấu hình")
    
    async def delete_white_label(self, config_id: str) -> Dict[str, str]:
        """Delete white label configuration"""
        try:
            # Check if config exists
            await self.get_white_label(config_id)
            
            # Soft delete by setting inactive
            self.supabase.table('white_label_configs')\
                .update({"is_active": False})\
                .eq('id', config_id)\
                .execute()
            
            return {"message": "Xóa cấu hình white label thành công"}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Delete white label error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi xóa cấu hình white label")
    
    async def get_theme_for_domain(self, domain: str) -> Dict[str, Any]:
        """Get theme configuration for a specific domain"""
        try:
            config = await self.get_white_label_by_domain(domain)
            
            if config:
                return {
                    'brand_name': config.brand_name,
                    'logo_url': config.logo_url,
                    'colors': {
                        'primary': config.primary_color,
                        'secondary': config.secondary_color,
                        'accent': config.accent_color
                    },
                    'theme': config.theme_config,
                    'custom_css': config.custom_css,
                    'custom_js': config.custom_js,
                    'contact_info': config.contact_info,
                    'social_links': config.social_links,
                    'features_enabled': config.features_enabled
                }
            
            # Return default theme if no white label config found
            return {
                'brand_name': 'FRM-AI',
                'logo_url': '/static/logo.png',
                'colors': {
                    'primary': '#1e40af',
                    'secondary': '#3b82f6',
                    'accent': '#10b981'
                },
                'theme': self.DEFAULT_THEME,
                'custom_css': None,
                'custom_js': None,
                'contact_info': {},
                'social_links': {},
                'features_enabled': self.AVAILABLE_FEATURES
            }
            
        except Exception as e:
            logger.error(f"Get theme for domain error: {e}")
            # Return default theme on error
            return {
                'brand_name': 'FRM-AI',
                'colors': {
                    'primary': '#1e40af',
                    'secondary': '#3b82f6',
                    'accent': '#10b981'
                },
                'theme': self.DEFAULT_THEME,
                'features_enabled': self.AVAILABLE_FEATURES
            }
    
    async def check_feature_enabled(self, domain: str, feature: str) -> bool:
        """Check if a feature is enabled for a domain"""
        try:
            config = await self.get_white_label_by_domain(domain)
            
            if config:
                return feature in config.features_enabled
            
            # All features enabled by default
            return feature in self.AVAILABLE_FEATURES
            
        except Exception as e:
            logger.error(f"Check feature enabled error: {e}")
            return True  # Allow access on error
    
    def get_available_features(self) -> List[Dict[str, str]]:
        """Get list of available features"""
        feature_descriptions = {
            'stock_analysis': 'Phân tích cổ phiếu cơ bản',
            'technical_analysis': 'Phân tích kỹ thuật',
            'portfolio_optimization': 'Tối ưu hóa danh mục',
            'news_analysis': 'Phân tích tin tức',
            'fundamental_scoring': 'Chấm điểm cơ bản',
            'ai_insights': 'Phân tích AI',
            'alerts': 'Cảnh báo thông minh',
            'social_features': 'Tính năng xã hội',
            'advanced_charts': 'Biểu đồ nâng cao',
            'real_time_data': 'Dữ liệu thời gian thực',
            'mobile_app': 'Ứng dụng di động',
            'api_access': 'Truy cập API',
            'white_label_branding': 'Thương hiệu riêng'
        }
        
        return [
            {'key': feature, 'description': feature_descriptions.get(feature, feature)}
            for feature in self.AVAILABLE_FEATURES
        ]

# Global white label manager
white_label_manager = WhiteLabelManager()
