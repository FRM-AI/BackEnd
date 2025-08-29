"""
Database Operations and Management
Các thao tác và quản lý cơ sở dữ liệu
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from supabase_config import get_supabase_client
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def get_system_settings(self) -> Dict[str, Any]:
        """Get all system settings"""
        try:
            result = self.supabase.table('system_settings').select("*").execute()
            
            settings = {}
            for setting in result.data:
                key = setting['key']
                value = setting['value']
                value_type = setting.get('value_type', 'string')
                
                # Convert value based on type
                if value_type == 'number':
                    try:
                        value = float(value) if '.' in value else int(value)
                    except:
                        value = 0
                elif value_type == 'boolean':
                    value = value.lower() in ('true', '1', 'yes')
                elif value_type == 'json':
                    import json
                    try:
                        value = json.loads(value)
                    except:
                        value = {}
                
                settings[key] = {
                    'value': value,
                    'description': setting.get('description'),
                    'is_public': setting.get('is_public', False)
                }
            
            return settings
            
        except Exception as e:
            logger.error(f"Get system settings error: {e}")
            return {}
    
    async def update_system_setting(self, key: str, value: str, description: Optional[str] = None,
                                  value_type: str = 'string', is_public: bool = False) -> bool:
        """Update or create system setting"""
        try:
            # Check if setting exists
            existing = self.supabase.table('system_settings').select("key").eq('key', key).execute()
            
            setting_data = {
                'key': key,
                'value': value,
                'value_type': value_type,
                'is_public': is_public
            }
            
            if description:
                setting_data['description'] = description
            
            if existing.data:
                # Update existing
                result = self.supabase.table('system_settings').update(setting_data).eq('key', key).execute()
            else:
                # Create new
                result = self.supabase.table('system_settings').insert(setting_data).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Update system setting error: {e}")
            return False
    
    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        try:
            stats = {}
            
            # User statistics
            users_result = self.supabase.table('users').select("id, created_at, is_active").execute()
            users = users_result.data
            
            stats['users'] = {
                'total': len(users),
                'active': len([u for u in users if u.get('is_active')]),
                'new_this_month': len([
                    u for u in users 
                    if datetime.fromisoformat(u['created_at'].replace('Z', '+00:00')).date() >= 
                    (datetime.now().replace(day=1)).date()
                ])
            }
            
            # Package statistics
            packages_result = self.supabase.table('user_packages').select("status, created_at").execute()
            packages = packages_result.data
            
            stats['packages'] = {
                'total_subscriptions': len(packages),
                'active_subscriptions': len([p for p in packages if p.get('status') == 'active']),
                'new_this_month': len([
                    p for p in packages 
                    if datetime.fromisoformat(p['created_at'].replace('Z', '+00:00')).date() >= 
                    (datetime.now().replace(day=1)).date()
                ])
            }
            
            # Wallet statistics
            wallets_result = self.supabase.table('wallets').select("balance, total_earned, total_spent").execute()
            wallets = wallets_result.data
            
            stats['wallet'] = {
                'total_balance': sum(float(w.get('balance', 0)) for w in wallets),
                'total_earned': sum(float(w.get('total_earned', 0)) for w in wallets),
                'total_spent': sum(float(w.get('total_spent', 0)) for w in wallets)
            }
            
            # Service usage statistics
            today = datetime.now().date().isoformat()
            week_ago = (datetime.now() - timedelta(days=7)).date().isoformat()
            
            usage_today_result = self.supabase.table('service_usage')\
                .select("id, coins_spent")\
                .gte('created_at', today)\
                .execute()
            
            usage_week_result = self.supabase.table('service_usage')\
                .select("id, coins_spent")\
                .gte('created_at', week_ago)\
                .execute()
            
            stats['service_usage'] = {
                'today': len(usage_today_result.data),
                'this_week': len(usage_week_result.data),
                'coins_spent_today': sum(int(u.get('coins_spent', 0)) for u in usage_today_result.data),
                'coins_spent_week': sum(int(u.get('coins_spent', 0)) for u in usage_week_result.data)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Get dashboard stats error: {e}")
            return {}
    
    async def get_financial_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get financial summary"""
        try:
            from_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Payment statistics
            payments_result = self.supabase.table('payments')\
                .select("amount, status, created_at")\
                .gte('created_at', from_date)\
                .execute()
            
            payments = payments_result.data
            completed_payments = [p for p in payments if p.get('status') == 'completed']
            
            # Transaction statistics
            transactions_result = self.supabase.table('wallet_transactions')\
                .select("transaction_type, amount, created_at")\
                .gte('created_at', from_date)\
                .execute()
            
            transactions = transactions_result.data
            
            # Calculate revenue
            revenue = sum(float(p.get('amount', 0)) for p in completed_payments)
            
            # Calculate coin distribution
            coin_added = sum(
                float(t.get('amount', 0)) for t in transactions 
                if t.get('transaction_type') in ['deposit', 'purchase_package', 'gift_received']
            )
            
            coin_spent = sum(
                float(t.get('amount', 0)) for t in transactions 
                if t.get('transaction_type') in ['spend_service', 'gift_sent', 'withdraw']
            )
            
            summary = {
                'period_days': days,
                'revenue': {
                    'total': revenue,
                    'transactions': len(completed_payments),
                    'average_per_transaction': revenue / len(completed_payments) if completed_payments else 0
                },
                'coins': {
                    'distributed': coin_added,
                    'spent': coin_spent,
                    'net_change': coin_added - coin_spent
                },
                'transactions': {
                    'total': len(transactions),
                    'by_type': {}
                }
            }
            
            # Group transactions by type
            for tx in transactions:
                tx_type = tx.get('transaction_type', 'unknown')
                if tx_type not in summary['transactions']['by_type']:
                    summary['transactions']['by_type'][tx_type] = {
                        'count': 0,
                        'total_amount': 0
                    }
                
                summary['transactions']['by_type'][tx_type]['count'] += 1
                summary['transactions']['by_type'][tx_type]['total_amount'] += float(tx.get('amount', 0))
            
            return summary
            
        except Exception as e:
            logger.error(f"Get financial summary error: {e}")
            return {}
    
    async def cleanup_old_data(self, days_to_keep: int = 365) -> Dict[str, int]:
        """Clean up old data (admin operation)"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
            
            cleanup_counts = {}
            
            # Clean old error logs
            error_logs_result = self.supabase.table('error_logs')\
                .delete()\
                .lt('created_at', cutoff_date)\
                .execute()
            cleanup_counts['error_logs'] = len(error_logs_result.data) if error_logs_result.data else 0
            
            # Clean old admin logs (keep more recent ones)
            admin_cutoff = (datetime.now() - timedelta(days=90)).isoformat()
            admin_logs_result = self.supabase.table('admin_logs')\
                .delete()\
                .lt('created_at', admin_cutoff)\
                .execute()
            cleanup_counts['admin_logs'] = len(admin_logs_result.data) if admin_logs_result.data else 0
            
            # Clean old read notifications (keep unread ones)
            notif_cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            notifications_result = self.supabase.table('notifications')\
                .delete()\
                .eq('is_read', True)\
                .lt('created_at', notif_cutoff)\
                .execute()
            cleanup_counts['notifications'] = len(notifications_result.data) if notifications_result.data else 0
            
            return cleanup_counts
            
        except Exception as e:
            logger.error(f"Cleanup old data error: {e}")
            return {}
    
    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export all user data (GDPR compliance)"""
        try:
            user_data = {}
            
            # User profile
            user_result = self.supabase.table('users').select("*").eq('id', user_id).execute()
            user_data['profile'] = user_result.data[0] if user_result.data else {}
            
            # Remove sensitive data
            if 'password_hash' in user_data['profile']:
                del user_data['profile']['password_hash']
            
            # Wallet data
            wallet_result = self.supabase.table('wallets').select("*").eq('user_id', user_id).execute()
            user_data['wallet'] = wallet_result.data[0] if wallet_result.data else {}
            
            # Transactions
            transactions_result = self.supabase.table('wallet_transactions').select("*").eq('user_id', user_id).execute()
            user_data['transactions'] = transactions_result.data
            
            # Packages
            packages_result = self.supabase.table('user_packages').select("*").eq('user_id', user_id).execute()
            user_data['packages'] = packages_result.data
            
            # Service usage
            usage_result = self.supabase.table('service_usage').select("*").eq('user_id', user_id).execute()
            user_data['service_usage'] = usage_result.data
            
            # Notifications
            notifications_result = self.supabase.table('notifications').select("*").eq('user_id', user_id).execute()
            user_data['notifications'] = notifications_result.data
            
            # Payments
            payments_result = self.supabase.table('payments').select("*").eq('user_id', user_id).execute()
            user_data['payments'] = payments_result.data
            
            return user_data
            
        except Exception as e:
            logger.error(f"Export user data error: {e}")
            return {}
    
    async def delete_user_data(self, user_id: str) -> bool:
        """Delete all user data (GDPR compliance - right to be forgotten)"""
        try:
            # This will cascade delete due to foreign key constraints
            # but we can also explicitly delete from each table
            
            # Delete in reverse order of dependencies
            tables_to_clean = [
                'notifications',
                'service_usage',
                'event_participants',
                'wallet_transactions',
                'wallets',
                'user_packages',
                'payments',
                'invites',
                'auth_providers',
                'user_roles',
                'admin_logs',
                'error_logs'
            ]
            
            for table in tables_to_clean:
                try:
                    self.supabase.table(table).delete().eq('user_id', user_id).execute()
                except Exception as e:
                    logger.warning(f"Error deleting from {table}: {e}")
            
            # Finally delete user
            user_result = self.supabase.table('users').delete().eq('id', user_id).execute()
            
            return bool(user_result.data)
            
        except Exception as e:
            logger.error(f"Delete user data error: {e}")
            return False

# Global database manager
database_manager = DatabaseManager()
