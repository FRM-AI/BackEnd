"""
Package and Subscription Management System
Hệ thống quản lý gói dịch vụ và đăng ký
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, date, timedelta
from fastapi import HTTPException
from supabase_config import get_supabase_client
import logging

logger = logging.getLogger(__name__)

# Pydantic Models
class Package(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    coin_amount: int
    duration_days: int
    features: List[str] = []
    is_active: bool = True
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime

class UserPackage(BaseModel):
    id: str
    user_id: str
    package_id: int
    start_date: date
    end_date: date
    status: str
    auto_renewal: bool = False
    purchased_price: Optional[float] = None
    coins_received: Optional[int] = None
    created_at: datetime
    updated_at: datetime

class PackageWithDetails(UserPackage):
    package_name: str
    package_description: Optional[str] = None
    package_features: List[str] = []

class PackageCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    coin_amount: int = Field(..., gt=0)
    duration_days: int = Field(..., gt=0)
    features: List[str] = []
    sort_order: int = 0

class PackageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    coin_amount: Optional[int] = None
    duration_days: Optional[int] = None
    features: Optional[List[str]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

class PackageManager:
    def __init__(self):
        self.supabase = get_supabase_client()
        
        # Package status
        self.PACKAGE_STATUS = {
            'active': 'Đang hoạt động',
            'expired': 'Đã hết hạn',
            'cancelled': 'Đã hủy',
            'suspended': 'Tạm ngưng'
        }
    
    async def get_all_packages(self, include_inactive: bool = False) -> List[Package]:
        """Get all available packages"""
        try:
            query = self.supabase.table('packages').select("*")
            
            if not include_inactive:
                query = query.eq('is_active', True)
            
            result = query.order('sort_order').order('price').execute()
            
            return [Package(**pkg) for pkg in result.data]
            
        except Exception as e:
            logger.error(f"Get packages error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy danh sách gói")
    
    async def get_package(self, package_id: int) -> Package:
        """Get package by ID"""
        try:
            result = self.supabase.table('packages').select("*").eq('id', package_id).execute()
            
            if not result.data:
                raise HTTPException(status_code=404, detail="Gói dịch vụ không tồn tại")
            
            return Package(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get package error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy thông tin gói")
    
    async def create_package(self, package_data: PackageCreate) -> Package:
        """Create new package (admin only)"""
        try:
            package_dict = package_data.dict()
            package_dict['is_active'] = True
            
            result = self.supabase.table('packages').insert(package_dict).execute()
            
            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể tạo gói dịch vụ")
            
            return Package(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Create package error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi tạo gói dịch vụ")
    
    async def update_package(self, package_id: int, update_data: PackageUpdate) -> Package:
        """Update package (admin only)"""
        try:
            # Check if package exists
            await self.get_package(package_id)
            
            # Prepare update data
            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
            
            if not update_dict:
                raise HTTPException(status_code=400, detail="Không có dữ liệu để cập nhật")
            
            result = self.supabase.table('packages').update(update_dict).eq('id', package_id).execute()
            
            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể cập nhật gói dịch vụ")
            
            return Package(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Update package error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi cập nhật gói dịch vụ")
    
    async def purchase_package(self, user_id: str, package_id: int) -> Dict[str, Any]:
        """Purchase package for user"""
        try:
            # Get package details
            package = await self.get_package(package_id)
            
            if not package.is_active:
                raise HTTPException(status_code=400, detail="Gói dịch vụ không khả dụng")
            
            # Check user balance
            from wallet_manager import wallet_manager
            wallet = await wallet_manager.get_wallet(user_id)
            
            if wallet.balance < package.price:
                raise HTTPException(status_code=400, detail="Số dư không đủ để mua gói dịch vụ")
            
            # Calculate dates
            start_date = date.today()
            end_date = start_date + timedelta(days=package.duration_days)
            
            # Create user package record
            user_package_data = {
                "user_id": user_id,
                "package_id": package_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "status": "active",
                "purchased_price": package.price,
                "coins_received": package.coin_amount,
                "auto_renewal": False
            }
            
            package_result = self.supabase.table('user_packages').insert(user_package_data).execute()
            
            if not package_result.data:
                raise HTTPException(status_code=500, detail="Không thể tạo đăng ký gói")
            
            user_package = package_result.data[0]
            
            # Deduct payment from wallet
            await wallet_manager.spend_coins(
                user_id, package.price, 'purchase_package',
                f"Mua gói {package.name}",
                'package', user_package['id']
            )
            
            # Add coins to wallet
            await wallet_manager.add_coins(
                user_id, package.coin_amount, 'purchase_package',
                f"Nhận {package.coin_amount} FRM Coins từ gói {package.name}",
                'package', user_package['id']
            )
            
            return {
                "success": True,
                "message": f"Mua gói {package.name} thành công",
                "user_package": UserPackage(**user_package),
                "package": package,
                "coins_received": package.coin_amount
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Purchase package error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi mua gói dịch vụ")
    
    async def get_user_packages(self, user_id: str, status: Optional[str] = None) -> List[PackageWithDetails]:
        """Get user's packages"""
        try:
            query = self.supabase.table('user_packages')\
                .select("*, packages(name, description, features)")\
                .eq('user_id', user_id)
            
            if status:
                query = query.eq('status', status)
            
            result = query.order('created_at', desc=True).execute()
            
            packages = []
            for item in result.data:
                package_info = item.pop('packages', {})
                package_data = {
                    **item,
                    'package_name': package_info.get('name', ''),
                    'package_description': package_info.get('description'),
                    'package_features': package_info.get('features', [])
                }
                packages.append(PackageWithDetails(**package_data))
            
            return packages
            
        except Exception as e:
            logger.error(f"Get user packages error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy danh sách gói đã mua")
    
    async def get_active_user_packages(self, user_id: str) -> List[PackageWithDetails]:
        """Get user's active packages"""
        return await self.get_user_packages(user_id, 'active')
    
    async def cancel_package(self, user_id: str, user_package_id: str) -> Dict[str, str]:
        """Cancel user package"""
        try:
            # Check if package belongs to user
            result = self.supabase.table('user_packages')\
                .select("*")\
                .eq('id', user_package_id)\
                .eq('user_id', user_id)\
                .execute()
            
            if not result.data:
                raise HTTPException(status_code=404, detail="Gói dịch vụ không tồn tại")
            
            user_package = result.data[0]
            
            if user_package['status'] != 'active':
                raise HTTPException(status_code=400, detail="Chỉ có thể hủy gói đang hoạt động")
            
            # Update package status
            self.supabase.table('user_packages')\
                .update({"status": "cancelled"})\
                .eq('id', user_package_id)\
                .execute()
            
            return {"message": "Hủy gói dịch vụ thành công"}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Cancel package error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi hủy gói dịch vụ")
    
    async def get_package_stats(self) -> Dict[str, Any]:
        """Get package statistics (admin only)"""
        try:
            # Get all packages
            packages_result = self.supabase.table('packages').select("*").execute()
            packages = packages_result.data
            
            # Get active subscriptions
            active_subs_result = self.supabase.table('user_packages')\
                .select("package_id, packages(name)")\
                .eq('status', 'active')\
                .execute()
            
            # Calculate stats
            stats = {
                'total_packages': len(packages),
                'active_packages': len([p for p in packages if p['is_active']]),
                'total_subscriptions': len(active_subs_result.data),
                'by_package': {}
            }
            
            # Count subscriptions by package
            for sub in active_subs_result.data:
                package_id = sub['package_id']
                package_name = sub['packages']['name'] if sub.get('packages') else f"Package {package_id}"
                
                if package_id not in stats['by_package']:
                    stats['by_package'][package_id] = {
                        'name': package_name,
                        'active_subscriptions': 0
                    }
                
                stats['by_package'][package_id]['active_subscriptions'] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Get package stats error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy thống kê gói")

# Global package manager
package_manager = PackageManager()
