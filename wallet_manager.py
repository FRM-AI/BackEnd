"""
Wallet and Transaction Management System
Hệ thống quản lý ví và giao dịch FRM Coin
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from fastapi import HTTPException
from supabase_config import get_supabase_client
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Pydantic Models
class WalletTransaction(BaseModel):
    id: str
    user_id: str
    transaction_type: str
    amount: float
    balance_before: float
    balance_after: float
    description: Optional[str] = None
    related_type: Optional[str] = None
    related_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    status: str = 'completed'
    created_at: datetime
    processed_at: Optional[datetime] = None

class WalletInfo(BaseModel):
    user_id: str
    balance: float
    locked_balance: float
    total_earned: float
    total_spent: float
    created_at: datetime
    updated_at: datetime

class TransactionRequest(BaseModel):
    amount: float = Field(..., gt=0)
    description: Optional[str] = None
    related_type: Optional[str] = None
    related_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class TransferRequest(BaseModel):
    recipient_email: str
    amount: float = Field(..., gt=0)
    description: Optional[str] = None

class WalletManager:
    def __init__(self):
        self.supabase = get_supabase_client(use_service_key=True)
        
        # Transaction types
        self.TRANSACTION_TYPES = {
            'deposit': 'Nạp tiền',
            'purchase_package': 'Mua gói dịch vụ',
            'gift_received': 'Nhận quà',
            'gift_sent': 'Gửi quà',
            'invite_bonus': 'Thưởng giới thiệu',
            'event_bonus': 'Thưởng sự kiện',
            'spend_service': 'Sử dụng dịch vụ',
            'refund': 'Hoàn tiền',
            'admin_adjustment': 'Điều chỉnh admin',
            'withdraw': 'Rút tiền',
            'transfer_sent': 'Chuyển tiền',
            'transfer_received': 'Nhận chuyển tiền'
        }
    
    async def ensure_wallet_exists(self, user_id: str) -> WalletInfo:
        """Ensure wallet exists for user, create if not exists"""
        try:
            result = self.supabase.table('wallets').select("*").eq('user_id', user_id).execute()
            
            if not result.data:
                # Create wallet for user
                wallet_data = {
                    "user_id": user_id,
                    "balance": 0,
                    "locked_balance": 0,
                    "total_earned": 0,
                    "total_spent": 0
                }
                
                create_result = self.supabase.table('wallets').insert(wallet_data).execute()
                
                if not create_result.data:
                    raise HTTPException(status_code=500, detail="Không thể tạo ví")
                
                return WalletInfo(**create_result.data[0])
            
            return WalletInfo(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ensure wallet exists error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi kiểm tra ví")
    
    async def get_wallet(self, user_id: str) -> WalletInfo:
        """Get wallet information"""
        try:
            # Use ensure_wallet_exists to automatically create if needed
            return await self.ensure_wallet_exists(user_id)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get wallet error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy thông tin ví")
    
    async def get_transactions(self, user_id: str, limit: int = 50, offset: int = 0, 
                             transaction_type: Optional[str] = None) -> List[WalletTransaction]:
        """Get user transaction history"""
        try:
            query = self.supabase.table('wallet_transactions').select("*").eq('user_id', user_id)
            
            if transaction_type:
                query = query.eq('transaction_type', transaction_type)
            
            result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
            
            return [WalletTransaction(**tx) for tx in result.data]
            
        except Exception as e:
            logger.error(f"Get transactions error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy lịch sử giao dịch")
    
    async def add_coins(self, user_id: str, amount: float, transaction_type: str, 
                       description: str, related_type: Optional[str] = None, 
                       related_id: Optional[str] = None, metadata: Optional[Dict] = None) -> WalletTransaction:
        """Add coins to user wallet"""
        try:
            # Validate transaction type
            if transaction_type not in ['deposit', 'gift_received', 'invite_bonus', 'event_bonus', 'refund', 'admin_adjustment', 'transfer_received']:
                raise HTTPException(status_code=400, detail="Loại giao dịch không hợp lệ")
            
            # Get current wallet balance
            wallet = await self.get_wallet(user_id)
            balance_before = wallet.balance
            balance_after = balance_before + amount
            
            # Create transaction with balance information
            transaction_data = {
                "user_id": user_id,
                "transaction_type": transaction_type,
                "amount": amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "description": description,
                "related_type": related_type,
                "related_id": related_id,
                "metadata": metadata,
                "status": "completed"
            }
            
            result = self.supabase.table('wallet_transactions').insert(transaction_data).execute()
            
            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể tạo giao dịch")
            
            # Update wallet balance
            wallet_update = {
                "balance": balance_after,
                "total_earned": wallet.total_earned + amount,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            wallet_result = self.supabase.table('wallets').update(wallet_update).eq('user_id', user_id).execute()
            
            if not wallet_result.data:
                logger.warning(f"Failed to update wallet balance for user {user_id}")
            
            return WalletTransaction(**result.data[0])
            
            return WalletTransaction(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Add coins error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi thêm coin")
    
    async def spend_coins(self, user_id: str, amount: float, transaction_type: str, 
                         description: str, related_type: Optional[str] = None, 
                         related_id: Optional[str] = None, metadata: Optional[Dict] = None) -> WalletTransaction:
        """Spend coins from user wallet"""
        try:
            # Validate transaction type
            if transaction_type not in ['spend_service', 'gift_sent', 'purchase_package', 'withdraw', 'transfer_sent']:
                raise HTTPException(status_code=400, detail="Loại giao dịch không hợp lệ")
            
            # Check balance first
            wallet = await self.get_wallet(user_id)
            if wallet.balance < amount:
                raise HTTPException(status_code=400, detail="Số dư không đủ")
            
            balance_before = wallet.balance
            balance_after = balance_before - amount
            
            # Create transaction with balance information
            transaction_data = {
                "user_id": user_id,
                "transaction_type": transaction_type,
                "amount": amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "description": description,
                "related_type": related_type,
                "related_id": related_id,
                "metadata": metadata,
                "status": "completed"
            }
            
            result = self.supabase.table('wallet_transactions').insert(transaction_data).execute()
            
            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể tạo giao dịch")
            
            # Update wallet balance
            wallet_update = {
                "balance": balance_after,
                "total_spent": wallet.total_spent + amount,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            wallet_result = self.supabase.table('wallets').update(wallet_update).eq('user_id', user_id).execute()
            
            if not wallet_result.data:
                logger.warning(f"Failed to update wallet balance for user {user_id}")
            
            return WalletTransaction(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Spend coins error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi trừ coin")
    
    async def transfer_coins(self, sender_id: str, recipient_email: str, amount: float, 
                           description: Optional[str] = None) -> Dict[str, Any]:
        """Transfer coins between users"""
        try:
            # Get recipient user
            recipient_result = self.supabase.table('users').select("id, email, full_name").eq('email', recipient_email).execute()
            
            if not recipient_result.data:
                raise HTTPException(status_code=404, detail="Người nhận không tồn tại")
            
            recipient = recipient_result.data[0]
            recipient_id = recipient['id']
            
            # Can't transfer to self
            if sender_id == recipient_id:
                raise HTTPException(status_code=400, detail="Không thể chuyển cho chính mình")
            
            # Check sender balance
            sender_wallet = await self.get_wallet(sender_id)
            if sender_wallet.balance < amount:
                raise HTTPException(status_code=400, detail="Số dư không đủ")
            
            # Create transfer description
            transfer_description = description or f"Chuyển {amount} FRM Coins"
            
            # Deduct from sender
            sender_tx = await self.spend_coins(
                sender_id, amount, 'transfer_sent', 
                f"{transfer_description} đến {recipient['email']}",
                'transfer', recipient_id
            )
            
            # Add to recipient
            recipient_tx = await self.add_coins(
                recipient_id, amount, 'transfer_received',
                f"{transfer_description} từ {sender_wallet.user_id}",
                'transfer', sender_id
            )
            
            return {
                "success": True,
                "message": "Chuyển tiền thành công",
                "sender_transaction": sender_tx,
                "recipient_transaction": recipient_tx,
                "recipient_info": {
                    "email": recipient['email'],
                    "full_name": recipient.get('full_name')
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Transfer coins error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi chuyển tiền")
    
    async def get_wallet_stats(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get wallet statistics"""
        try:
            # Get wallet info
            wallet = await self.get_wallet(user_id)
            
            # Get transactions in period
            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            transactions_result = self.supabase.table('wallet_transactions')\
                .select("transaction_type, amount, created_at")\
                .eq('user_id', user_id)\
                .gte('created_at', from_date)\
                .execute()
            
            transactions = transactions_result.data
            
            # Calculate stats
            stats = {
                'current_balance': wallet.balance,
                'locked_balance': wallet.locked_balance,
                'total_earned': wallet.total_earned,
                'total_spent': wallet.total_spent,
                'period_days': days,
                'period_stats': {
                    'total_income': 0,
                    'total_spending': 0,
                    'transaction_count': len(transactions),
                    'by_type': {}
                }
            }
            
            # Process transactions
            income_types = ['deposit', 'gift_received', 'invite_bonus', 'event_bonus', 'refund', 'transfer_received']
            spending_types = ['spend_service', 'gift_sent', 'purchase_package', 'withdraw', 'transfer_sent']
            
            for tx in transactions:
                tx_type = tx['transaction_type']
                amount = tx['amount']
                
                if tx_type not in stats['period_stats']['by_type']:
                    stats['period_stats']['by_type'][tx_type] = {
                        'count': 0,
                        'total_amount': 0,
                        'description': self.TRANSACTION_TYPES.get(tx_type, tx_type)
                    }
                
                stats['period_stats']['by_type'][tx_type]['count'] += 1
                stats['period_stats']['by_type'][tx_type]['total_amount'] += amount
                
                if tx_type in income_types:
                    stats['period_stats']['total_income'] += amount
                elif tx_type in spending_types:
                    stats['period_stats']['total_spending'] += amount
            
            return stats
            
        except Exception as e:
            logger.error(f"Get wallet stats error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi khi lấy thống kê ví")

# Global wallet manager
wallet_manager = WalletManager()
