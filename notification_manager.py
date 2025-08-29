"""
Notification Manager for FRM-AI
Quản lý thông báo hệ thống, push notifications và email alerts
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field, EmailStr, validator
from supabase import Client
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from pathlib import Path
import aiosmtplib
import aiofiles
from jinja2 import Template, Environment, FileSystemLoader
import uuid

# Import configurations
from supabase_config import get_supabase_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================================
# PYDANTIC MODELS
# ================================

class NotificationBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Tiêu đề thông báo")
    message: str = Field(..., min_length=1, max_length=2000, description="Nội dung thông báo")
    notification_type: str = Field(default="info", description="Loại thông báo")
    action_url: Optional[str] = Field(None, description="URL hành động")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata bổ sung")

    @validator('notification_type')
    def validate_notification_type(cls, v):
        allowed_types = ['info', 'success', 'warning', 'error', 'promotion', 'system']
        if v not in allowed_types:
            raise ValueError(f'notification_type must be one of {allowed_types}')
        return v

class NotificationCreate(NotificationBase):
    user_id: str = Field(..., description="ID người dùng nhận thông báo")

class BulkNotificationCreate(NotificationBase):
    user_ids: Optional[List[str]] = Field(None, description="Danh sách ID người dùng")
    user_filter: Optional[Dict[str, Any]] = Field(None, description="Bộ lọc người dùng")
    send_to_all: bool = Field(default=False, description="Gửi cho tất cả người dùng")

class Notification(NotificationBase):
    id: str
    user_id: str
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class EmailTemplate(BaseModel):
    subject: str
    html_body: str
    text_body: Optional[str] = None
    template_vars: Dict[str, Any] = Field(default_factory=dict)

class PushNotificationRequest(BaseModel):
    title: str
    body: str
    icon: Optional[str] = None
    badge: Optional[str] = None
    image: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, str]]] = None

class NotificationSettings(BaseModel):
    email_notifications: bool = True
    push_notifications: bool = True
    sms_notifications: bool = False
    notification_types: Dict[str, bool] = Field(default_factory=lambda: {
        'system': True,
        'promotion': True,
        'warning': True,
        'error': True,
        'info': True,
        'success': True
    })
    quiet_hours_start: Optional[str] = Field(None, pattern=r'^\d{2}:\d{2}$')
    quiet_hours_end: Optional[str] = Field(None, pattern=r'^\d{2}:\d{2}$')

# ================================
# NOTIFICATION MANAGER CLASS
# ================================

class NotificationManager:
    def __init__(self):
        self.supabase: Client = get_supabase_client()
        self.email_config = {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'smtp_username': os.getenv('SMTP_USERNAME', ''),
            'smtp_password': os.getenv('SMTP_PASSWORD', ''),
            'from_email': os.getenv('FROM_EMAIL', 'noreply@frm-ai.com'),
            'from_name': os.getenv('FROM_NAME', 'FRM-AI System')
        }
        
        # Setup template environment
        template_dir = Path(__file__).parent / "templates" / "notifications"
        if template_dir.exists():
            self.template_env = Environment(loader=FileSystemLoader(str(template_dir)))
        else:
            self.template_env = Environment(loader=FileSystemLoader('.'))
        
        logger.info("NotificationManager initialized")

    # ================================
    # CORE NOTIFICATION METHODS
    # ================================

    async def create_notification(
        self, 
        user_id: str, 
        title: str, 
        message: str,
        notification_type: str = "info",
        action_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        send_email: bool = False,
        send_push: bool = False
    ) -> Notification:
        """Tạo thông báo mới cho người dùng"""
        try:
            notification_data = {
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'title': title,
                'message': message,
                'notification_type': notification_type,
                'action_url': action_url,
                'metadata': metadata or {},
                'is_read': False,
                'created_at': datetime.utcnow().isoformat()
            }

            # Insert vào database
            result = self.supabase.table('notifications').insert(notification_data).execute()
            
            if not result.data:
                raise Exception("Failed to create notification")

            notification = Notification(**result.data[0])
            
            # Gửi email nếu được yêu cầu
            if send_email:
                asyncio.create_task(self._send_email_notification(user_id, notification))
            
            # Gửi push notification nếu được yêu cầu
            if send_push:
                asyncio.create_task(self._send_push_notification(user_id, notification))
            
            logger.info(f"Created notification {notification.id} for user {user_id}")
            return notification

        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            raise Exception(f"Failed to create notification: {str(e)}")

    async def get_user_notifications(
        self, 
        user_id: str, 
        limit: int = 50, 
        offset: int = 0,
        unread_only: bool = False,
        notification_type: Optional[str] = None
    ) -> List[Notification]:
        """Lấy danh sách thông báo của người dùng"""
        try:
            query = self.supabase.table('notifications').select('*').eq('user_id', user_id)
            
            if unread_only:
                query = query.eq('is_read', False)
            
            if notification_type:
                query = query.eq('notification_type', notification_type)
            
            query = query.order('created_at', desc=True).range(offset, offset + limit - 1)
            
            result = query.execute()
            
            notifications = [Notification(**item) for item in result.data]
            return notifications

        except Exception as e:
            logger.error(f"Error getting user notifications: {str(e)}")
            return []

    async def mark_as_read(self, user_id: str, notification_id: str) -> bool:
        """Đánh dấu thông báo đã đọc"""
        try:
            result = self.supabase.table('notifications').update({
                'is_read': True,
                'read_at': datetime.utcnow().isoformat()
            }).eq('id', notification_id).eq('user_id', user_id).execute()
            
            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}")
            return False

    async def mark_all_as_read(self, user_id: str) -> bool:
        """Đánh dấu tất cả thông báo đã đọc"""
        try:
            result = self.supabase.table('notifications').update({
                'is_read': True,
                'read_at': datetime.utcnow().isoformat()
            }).eq('user_id', user_id).eq('is_read', False).execute()
            
            return True

        except Exception as e:
            logger.error(f"Error marking all notifications as read: {str(e)}")
            return False

    async def delete_notification(self, user_id: str, notification_id: str) -> bool:
        """Xóa thông báo"""
        try:
            result = self.supabase.table('notifications').delete().eq(
                'id', notification_id
            ).eq('user_id', user_id).execute()
            
            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error deleting notification: {str(e)}")
            return False

    async def get_unread_count(self, user_id: str) -> int:
        """Lấy số lượng thông báo chưa đọc"""
        try:
            result = self.supabase.table('notifications').select(
                'id', count='exact'
            ).eq('user_id', user_id).eq('is_read', False).execute()
            
            return result.count or 0

        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return 0

    # ================================
    # BULK NOTIFICATION METHODS
    # ================================

    async def create_bulk_notifications(self, notification_data: BulkNotificationCreate) -> Dict[str, Any]:
        """Tạo thông báo hàng loạt"""
        try:
            user_ids = []
            
            if notification_data.send_to_all:
                # Lấy tất cả user IDs
                result = self.supabase.table('users').select('id').eq('is_active', True).execute()
                user_ids = [user['id'] for user in result.data]
            
            elif notification_data.user_ids:
                user_ids = notification_data.user_ids
            
            elif notification_data.user_filter:
                # Áp dụng bộ lọc để tìm users
                user_ids = await self._filter_users(notification_data.user_filter)
            
            if not user_ids:
                return {'success': False, 'message': 'No users found', 'count': 0}
            
            # Tạo notifications hàng loạt
            notifications_data = []
            for user_id in user_ids:
                notifications_data.append({
                    'id': str(uuid.uuid4()),
                    'user_id': user_id,
                    'title': notification_data.title,
                    'message': notification_data.message,
                    'notification_type': notification_data.notification_type,
                    'action_url': notification_data.action_url,
                    'metadata': notification_data.metadata,
                    'is_read': False,
                    'created_at': datetime.utcnow().isoformat()
                })
            
            # Insert hàng loạt
            result = self.supabase.table('notifications').insert(notifications_data).execute()
            
            success_count = len(result.data) if result.data else 0
            
            logger.info(f"Created {success_count} bulk notifications")
            
            return {
                'success': True,
                'message': f'Created {success_count} notifications',
                'count': success_count,
                'user_ids': user_ids
            }

        except Exception as e:
            logger.error(f"Error creating bulk notifications: {str(e)}")
            return {'success': False, 'message': str(e), 'count': 0}

    async def _filter_users(self, user_filter: Dict[str, Any]) -> List[str]:
        """Lọc users dựa trên criteria"""
        try:
            query = self.supabase.table('users').select('id')
            
            # Áp dụng các điều kiện lọc
            if 'is_active' in user_filter:
                query = query.eq('is_active', user_filter['is_active'])
            
            if 'email_verified' in user_filter:
                query = query.eq('email_verified', user_filter['email_verified'])
            
            if 'created_after' in user_filter:
                query = query.gte('created_at', user_filter['created_after'])
            
            if 'created_before' in user_filter:
                query = query.lte('created_at', user_filter['created_before'])
            
            if 'has_package' in user_filter and user_filter['has_package']:
                # Users có gói active
                package_users = self.supabase.table('user_packages').select('user_id').eq(
                    'status', 'active'
                ).gte('end_date', datetime.utcnow().date().isoformat()).execute()
                
                package_user_ids = [p['user_id'] for p in package_users.data]
                if package_user_ids:
                    query = query.in_('id', package_user_ids)
                else:
                    return []
            
            result = query.execute()
            return [user['id'] for user in result.data]

        except Exception as e:
            logger.error(f"Error filtering users: {str(e)}")
            return []

    # ================================
    # EMAIL NOTIFICATION METHODS
    # ================================

    async def _send_email_notification(self, user_id: str, notification: Notification):
        """Gửi email thông báo"""
        try:
            # Lấy thông tin user
            user_result = self.supabase.table('users').select('email, full_name').eq('id', user_id).execute()
            if not user_result.data:
                return
            
            user = user_result.data[0]
            
            # Kiểm tra settings email của user
            if not await self._should_send_email(user_id, notification.notification_type):
                return
            
            # Tạo email content
            email_template = self._get_email_template(notification.notification_type)
            
            template_vars = {
                'user_name': user.get('full_name', 'Người dùng'),
                'notification_title': notification.title,
                'notification_message': notification.message,
                'action_url': notification.action_url,
                'notification_type': notification.notification_type,
                'timestamp': notification.created_at.strftime('%d/%m/%Y %H:%M'),
                'unsubscribe_url': f"https://frm-ai.com/unsubscribe?user_id={user_id}"
            }
            
            subject = email_template['subject'].format(**template_vars)
            html_body = email_template['html_body'].format(**template_vars)
            
            # Gửi email
            await self._send_email(user['email'], subject, html_body)
            
            logger.info(f"Sent email notification to {user['email']}")

        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")

    async def _send_email(self, to_email: str, subject: str, html_body: str, text_body: Optional[str] = None):
        """Gửi email sử dụng SMTP async"""
        try:
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = f"{self.email_config['from_name']} <{self.email_config['from_email']}>"
            message['To'] = to_email
            
            # Text version
            if text_body:
                text_part = MIMEText(text_body, 'plain', 'utf-8')
                message.attach(text_part)
            
            # HTML version
            html_part = MIMEText(html_body, 'html', 'utf-8')
            message.attach(html_part)
            
            # Gửi email async
            await aiosmtplib.send(
                message,
                hostname=self.email_config['smtp_server'],
                port=self.email_config['smtp_port'],
                start_tls=True,
                username=self.email_config['smtp_username'],
                password=self.email_config['smtp_password']
            )

        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            raise

    def _get_email_template(self, notification_type: str) -> Dict[str, str]:
        """Lấy template email theo loại thông báo"""
        templates = {
            'system': {
                'subject': '[FRM-AI] Thông báo hệ thống: {notification_title}',
                'html_body': '''
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                            <h2 style="color: #2c3e50; margin-bottom: 10px;">🔔 Thông báo hệ thống</h2>
                            <p>Xin chào <strong>{user_name}</strong>,</p>
                        </div>
                        
                        <div style="background: white; padding: 20px; border-left: 4px solid #3498db; margin-bottom: 20px;">
                            <h3 style="color: #2c3e50; margin-bottom: 15px;">{notification_title}</h3>
                            <p style="margin-bottom: 15px;">{notification_message}</p>
                            
                            {{% if action_url %}}
                            <a href="{action_url}" style="background: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                                Xem chi tiết
                            </a>
                            {{% endif %}}
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; font-size: 12px; color: #666;">
                            <p>Thời gian: {timestamp}</p>
                            <p>Đây là email tự động từ hệ thống FRM-AI. Vui lòng không reply email này.</p>
                            <p><a href="{unsubscribe_url}">Hủy đăng ký nhận email</a></p>
                        </div>
                    </div>
                </body>
                </html>
                '''
            },
            'success': {
                'subject': '[FRM-AI] ✅ {notification_title}',
                'html_body': '''
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: #d4edda; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                            <h2 style="color: #155724; margin-bottom: 10px;">✅ Thành công!</h2>
                            <p>Xin chào <strong>{user_name}</strong>,</p>
                        </div>
                        
                        <div style="background: white; padding: 20px; border-left: 4px solid #28a745; margin-bottom: 20px;">
                            <h3 style="color: #155724; margin-bottom: 15px;">{notification_title}</h3>
                            <p style="margin-bottom: 15px;">{notification_message}</p>
                            
                            {{% if action_url %}}
                            <a href="{action_url}" style="background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                                Xem chi tiết
                            </a>
                            {{% endif %}}
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; font-size: 12px; color: #666;">
                            <p>Thời gian: {timestamp}</p>
                            <p><a href="{unsubscribe_url}">Hủy đăng ký nhận email</a></p>
                        </div>
                    </div>
                </body>
                </html>
                '''
            },
            'warning': {
                'subject': '[FRM-AI] ⚠️ Cảnh báo: {notification_title}',
                'html_body': '''
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: #fff3cd; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                            <h2 style="color: #856404; margin-bottom: 10px;">⚠️ Cảnh báo</h2>
                            <p>Xin chào <strong>{user_name}</strong>,</p>
                        </div>
                        
                        <div style="background: white; padding: 20px; border-left: 4px solid #ffc107; margin-bottom: 20px;">
                            <h3 style="color: #856404; margin-bottom: 15px;">{notification_title}</h3>
                            <p style="margin-bottom: 15px;">{notification_message}</p>
                            
                            {{% if action_url %}}
                            <a href="{action_url}" style="background: #ffc107; color: #212529; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                                Xử lý ngay
                            </a>
                            {{% endif %}}
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; font-size: 12px; color: #666;">
                            <p>Thời gian: {timestamp}</p>
                            <p><a href="{unsubscribe_url}">Hủy đăng ký nhận email</a></p>
                        </div>
                    </div>
                </body>
                </html>
                '''
            },
            'error': {
                'subject': '[FRM-AI] 🚨 Lỗi: {notification_title}',
                'html_body': '''
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: #f8d7da; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                            <h2 style="color: #721c24; margin-bottom: 10px;">🚨 Lỗi xảy ra</h2>
                            <p>Xin chào <strong>{user_name}</strong>,</p>
                        </div>
                        
                        <div style="background: white; padding: 20px; border-left: 4px solid #dc3545; margin-bottom: 20px;">
                            <h3 style="color: #721c24; margin-bottom: 15px;">{notification_title}</h3>
                            <p style="margin-bottom: 15px;">{notification_message}</p>
                            
                            {{% if action_url %}}
                            <a href="{action_url}" style="background: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                                Xem chi tiết
                            </a>
                            {{% endif %}}
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; font-size: 12px; color: #666;">
                            <p>Thời gian: {timestamp}</p>
                            <p>Nếu cần hỗ trợ, vui lòng liên hệ: support@frm-ai.com</p>
                            <p><a href="{unsubscribe_url}">Hủy đăng ký nhận email</a></p>
                        </div>
                    </div>
                </body>
                </html>
                '''
            },
            'promotion': {
                'subject': '[FRM-AI] 🎉 Khuyến mãi: {notification_title}',
                'html_body': '''
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 8px; margin-bottom: 20px; color: white;">
                            <h2 style="color: white; margin-bottom: 10px;">🎉 Khuyến mãi đặc biệt!</h2>
                            <p>Xin chào <strong>{user_name}</strong>,</p>
                        </div>
                        
                        <div style="background: white; padding: 20px; border-left: 4px solid #667eea; margin-bottom: 20px;">
                            <h3 style="color: #667eea; margin-bottom: 15px;">{notification_title}</h3>
                            <p style="margin-bottom: 15px;">{notification_message}</p>
                            
                            {{% if action_url %}}
                            <a href="{action_url}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                                Nhận khuyến mãi ngay!
                            </a>
                            {{% endif %}}
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; font-size: 12px; color: #666;">
                            <p>Thời gian: {timestamp}</p>
                            <p><a href="{unsubscribe_url}">Hủy đăng ký nhận email khuyến mãi</a></p>
                        </div>
                    </div>
                </body>
                </html>
                '''
            }
        }
        
        return templates.get(notification_type, templates['system'])

    async def _should_send_email(self, user_id: str, notification_type: str) -> bool:
        """Kiểm tra xem có nên gửi email cho user không"""
        try:
            # Lấy settings của user (có thể implement sau)
            # Tạm thời return True cho tất cả
            return True
            
        except Exception as e:
            logger.error(f"Error checking email settings: {str(e)}")
            return False

    # ================================
    # PUSH NOTIFICATION METHODS
    # ================================

    async def _send_push_notification(self, user_id: str, notification: Notification):
        """Gửi push notification (có thể integrate với Firebase, OneSignal, etc.)"""
        try:
            # Placeholder cho push notification implementation
            # Có thể integrate với Firebase Cloud Messaging hoặc OneSignal
            
            push_data = {
                'title': notification.title,
                'body': notification.message,
                'icon': '/static/icon-192x192.png',
                'badge': '/static/badge.png',
                'data': {
                    'notification_id': notification.id,
                    'action_url': notification.action_url,
                    'type': notification.notification_type
                }
            }
            
            # TODO: Implement actual push notification sending
            logger.info(f"Would send push notification to user {user_id}: {push_data}")
            
        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")

    # ================================
    # PREDEFINED NOTIFICATION HELPERS
    # ================================

    async def notify_welcome(self, user_id: str, user_name: str) -> Notification:
        """Thông báo chào mừng user mới"""
        return await self.create_notification(
            user_id=user_id,
            title="Chào mừng đến với FRM-AI! 🎉",
            message=f"Xin chào {user_name}! Cảm ơn bạn đã tham gia FRM-AI. Hãy khám phá các tính năng phân tích tài chính mạnh mẽ của chúng tôi!",
            notification_type="success",
            action_url="/dashboard",
            metadata={"welcome": True},
            send_email=True
        )

    async def notify_package_purchased(self, user_id: str, package_name: str, coins_received: int) -> Notification:
        """Thông báo mua gói thành công"""
        return await self.create_notification(
            user_id=user_id,
            title="Mua gói dịch vụ thành công! ✅",
            message=f"Bạn đã mua thành công gói '{package_name}' và nhận được {coins_received} FRM Coins. Hãy bắt đầu sử dụng các dịch vụ premium!",
            notification_type="success",
            action_url="/packages",
            metadata={"package_name": package_name, "coins_received": coins_received},
            send_email=True
        )

    async def notify_low_coins(self, user_id: str, current_balance: float) -> Notification:
        """Thông báo coins sắp hết"""
        return await self.create_notification(
            user_id=user_id,
            title="Coins sắp hết! ⚠️",
            message=f"Số dư FRM Coins của bạn chỉ còn {current_balance}. Hãy nạp thêm để tiếp tục sử dụng dịch vụ!",
            notification_type="warning",
            action_url="/wallet",
            metadata={"current_balance": current_balance},
            send_email=True
        )

    async def notify_service_limit_reached(self, user_id: str, service_type: str) -> Notification:
        """Thông báo đã đạt giới hạn sử dụng dịch vụ"""
        return await self.create_notification(
            user_id=user_id,
            title="Đã đạt giới hạn sử dụng! 🚫",
            message=f"Bạn đã đạt giới hạn sử dụng dịch vụ '{service_type}' trong ngày. Hãy nâng cấp gói để sử dụng nhiều hơn!",
            notification_type="warning",
            action_url="/packages",
            metadata={"service_type": service_type}
        )

    async def notify_invite_bonus(self, user_id: str, invitee_name: str, bonus_amount: int) -> Notification:
        """Thông báo nhận bonus từ mời bạn"""
        return await self.create_notification(
            user_id=user_id,
            title="Nhận bonus mời bạn! 🎁",
            message=f"Bạn đã nhận {bonus_amount} FRM Coins từ việc mời {invitee_name} tham gia FRM-AI!",
            notification_type="success",
            action_url="/wallet",
            metadata={"invitee_name": invitee_name, "bonus_amount": bonus_amount}
        )

    async def notify_payment_successful(self, user_id: str, amount: float, coins_received: int) -> Notification:
        """Thông báo thanh toán thành công"""
        return await self.create_notification(
            user_id=user_id,
            title="Thanh toán thành công! 💰",
            message=f"Thanh toán {amount:,.0f} VND thành công. Bạn đã nhận {coins_received} FRM Coins vào ví!",
            notification_type="success",
            action_url="/wallet",
            metadata={"amount": amount, "coins_received": coins_received},
            send_email=True
        )

    async def notify_system_maintenance(self, title: str = None, message: str = None, start_time: datetime = None) -> Dict[str, Any]:
        """Thông báo bảo trì hệ thống cho tất cả users"""
        if not title:
            title = "Thông báo bảo trì hệ thống 🔧"
        
        if not message:
            start_str = start_time.strftime("%d/%m/%Y %H:%M") if start_time else "sắp tới"
            message = f"Hệ thống sẽ được bảo trì vào {start_str}. Trong thời gian này, một số tính năng có thể không khả dụng. Cảm ơn sự thông cảm của bạn!"
        
        return await self.create_bulk_notifications(BulkNotificationCreate(
            title=title,
            message=message,
            notification_type="system",
            send_to_all=True,
            metadata={"maintenance": True, "start_time": start_time.isoformat() if start_time else None}
        ))

    # ================================
    # CLEANUP METHODS
    # ================================

    async def cleanup_old_notifications(self, days_to_keep: int = 90) -> Dict[str, Any]:
        """Dọn dẹp thông báo cũ"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Xóa thông báo cũ đã đọc
            result = self.supabase.table('notifications').delete().eq(
                'is_read', True
            ).lt('created_at', cutoff_date.isoformat()).execute()
            
            deleted_count = len(result.data) if result.data else 0
            
            logger.info(f"Cleaned up {deleted_count} old notifications")
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_date.isoformat()
            }

        except Exception as e:
            logger.error(f"Error cleaning up notifications: {str(e)}")
            return {'success': False, 'error': str(e)}

    # ================================
    # STATISTICS METHODS
    # ================================

    async def get_notification_stats(self, days: int = 30) -> Dict[str, Any]:
        """Lấy thống kê thông báo"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Tổng số thông báo
            total_result = self.supabase.table('notifications').select(
                'id', count='exact'
            ).gte('created_at', cutoff_date.isoformat()).execute()
            
            # Thông báo theo loại
            type_result = self.supabase.table('notifications').select(
                'notification_type'
            ).gte('created_at', cutoff_date.isoformat()).execute()
            
            type_counts = {}
            for item in type_result.data:
                ntype = item['notification_type']
                type_counts[ntype] = type_counts.get(ntype, 0) + 1
            
            # Tỷ lệ đọc
            read_result = self.supabase.table('notifications').select(
                'is_read'
            ).gte('created_at', cutoff_date.isoformat()).execute()
            
            total_notifications = len(read_result.data)
            read_notifications = sum(1 for item in read_result.data if item['is_read'])
            read_rate = (read_notifications / total_notifications * 100) if total_notifications > 0 else 0
            
            return {
                'total_notifications': total_result.count or 0,
                'by_type': type_counts,
                'read_rate': round(read_rate, 2),
                'read_count': read_notifications,
                'unread_count': total_notifications - read_notifications,
                'period_days': days
            }

        except Exception as e:
            logger.error(f"Error getting notification stats: {str(e)}")
            return {}

# ================================
# GLOBAL INSTANCE
# ================================

# Tạo instance global để sử dụng trong toàn bộ ứng dụng
notification_manager = NotificationManager()

# ================================
# CONVENIENCE FUNCTIONS
# ================================

async def send_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    action_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    send_email: bool = False,
    send_push: bool = False
) -> Notification:
    """Convenience function để gửi thông báo"""
    return await notification_manager.create_notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
        metadata=metadata,
        send_email=send_email,
        send_push=send_push
    )

async def send_bulk_notification(
    title: str,
    message: str,
    notification_type: str = "info",
    user_ids: Optional[List[str]] = None,
    send_to_all: bool = False,
    user_filter: Optional[Dict[str, Any]] = None,
    action_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Convenience function để gửi thông báo hàng loạt"""
    return await notification_manager.create_bulk_notifications(
        BulkNotificationCreate(
            title=title,
            message=message,
            notification_type=notification_type,
            user_ids=user_ids,
            send_to_all=send_to_all,
            user_filter=user_filter,
            action_url=action_url,
            metadata=metadata
        )
    )

# Export các class và function chính
__all__ = [
    'NotificationManager',
    'notification_manager',
    'Notification',
    'NotificationCreate',
    'BulkNotificationCreate',
    'NotificationSettings',
    'send_notification',
    'send_bulk_notification'
]
