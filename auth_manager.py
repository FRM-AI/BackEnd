"""
Authentication and User Management System
Hệ thống xác thực và quản lý người dùng - Sử dụng Session Cookies
"""

from fastapi import HTTPException, Depends, Request, Cookie, Response
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta, timezone
import uuid
import bcrypt
import secrets
import os
from supabase_config import get_supabase_client
import logging

logger = logging.getLogger(__name__)

# Session Configuration
SESSION_SECRET = os.getenv("SESSION_SECRET", "your-session-secret-key-change-in-production")
SESSION_EXPIRATION_HOURS = 24
COOKIE_NAME = "session_id"

# Pydantic Models
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)

class User(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    email_verified: bool = False
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class UserWithWallet(User):
    balance: float = 0
    locked_balance: float = 0
    total_earned: float = 0
    total_spent: float = 0

# Authentication Manager
class AuthManager:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.supabase_admin = get_supabase_client(use_service_key=True)  # For admin operations
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    def create_session_id(self) -> str:
        """Create a secure session ID"""
        return secrets.token_urlsafe(32)
    
    async def create_session(self, user_id: str, session_id: str) -> None:
        """Create a session in database"""
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_EXPIRATION_HOURS)
            
            session_data = {
                "id": session_id,
                "user_id": user_id,
                "expires_at": expires_at.isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_active": True
            }
            
            # Delete old sessions for this user (optional - keep only one session per user)
            self.supabase_admin.table('user_sessions').delete().eq('user_id', user_id).execute()
            
            # Create new session
            self.supabase_admin.table('user_sessions').insert(session_data).execute()
            
        except Exception as e:
            logger.error(f"Create session error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi tạo session")
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session from database"""
        try:
            result = self.supabase_admin.table('user_sessions')\
                .select("*")\
                .eq('id', session_id)\
                .eq('is_active', True)\
                .execute()
            
            if not result.data:
                return None
            
            session = result.data[0]
            
            # Check if session is expired
            expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
            if expires_at < datetime.now(timezone.utc):
                # Delete expired session
                await self.delete_session(session_id)
                return None
            
            return session
            
        except Exception as e:
            logger.error(f"Get session error: {e}")
            return None
    
    async def delete_session(self, session_id: str) -> None:
        """Delete session from database"""
        try:
            self.supabase_admin.table('user_sessions')\
                .update({"is_active": False})\
                .eq('id', session_id)\
                .execute()
        except Exception as e:
            logger.error(f"Delete session error: {e}")
    
    async def extend_session(self, session_id: str) -> None:
        """Extend session expiration"""
        try:
            new_expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_EXPIRATION_HOURS)
            
            self.supabase_admin.table('user_sessions')\
                .update({"expires_at": new_expires_at.isoformat()})\
                .eq('id', session_id)\
                .eq('is_active', True)\
                .execute()
                
        except Exception as e:
            logger.error(f"Extend session error: {e}")
    
    async def register_user(self, user_data: UserRegister) -> Dict[str, Any]:
        """Register new user"""
        try:
            # Check if email already exists
            existing_user = self.supabase.table('users').select("id").eq('email', user_data.email).execute()
            if existing_user.data:
                raise HTTPException(status_code=400, detail="Email đã được sử dụng")
            
            # Hash password
            hashed_password = self.hash_password(user_data.password)
            
            # Create user
            user_insert = {
                "email": user_data.email,
                "password_hash": hashed_password,
                "full_name": user_data.full_name,
                "phone": user_data.phone,
                "is_active": True,
                "email_verified": False
            }
            
            result = self.supabase_admin.table('users').insert(user_insert).execute()
            
            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể tạo tài khoản")
            
            user = result.data[0]
            
            # Assign default role
            role_result = self.supabase.table('roles').select("id").eq('name', 'user').execute()
            if role_result.data:
                self.supabase.table('user_roles').insert({
                    "user_id": user['id'],
                    "role_id": role_result.data[0]['id']
                }).execute()
            
            # Create session
            session_id = self.create_session_id()
            await self.create_session(user['id'], session_id)
            
            return {
                "user": User(**user),
                "session_id": session_id,
                "message": "Đăng ký thành công"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Registration error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi đăng ký")

    async def login_user(self, login_data: UserLogin) -> Dict[str, Any]:
        """Login user"""
        try:
            # Get user by email
            result = self.supabase.table('users').select("*").eq('email', login_data.email).execute()

            if not result.data:
                raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
            
            user = result.data[0]
            
            # Check if user is active
            if not user.get('is_active'):
                raise HTTPException(status_code=401, detail="Tài khoản đã bị vô hiệu hóa")
            
            # Verify password
            if not self.verify_password(login_data.password, user['password_hash']):
                raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
            
            # Update last login
            self.supabase.table('users').update({
                "last_login_at": datetime.now().isoformat()
            }).eq('id', user['id']).execute()
            
            # Get user with wallet info
            wallet_result = self.supabase.table('wallets').select("*").eq('user_id', user['id']).execute()
            wallet = wallet_result.data[0] if wallet_result.data else {}
            
            # Create session
            session_id = self.create_session_id()
            await self.create_session(user['id'], session_id)
            
            # Combine user and wallet data
            user_with_wallet = {**user, **wallet}
            
            return {
                "user": UserWithWallet(**user_with_wallet),
                "session_id": session_id,
                "message": "Đăng nhập thành công"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi đăng nhập")
    
    async def get_current_user(self, session_id: str) -> UserWithWallet:
        """Get current user from session"""
        try:
            # Get session
            session = await self.get_session(session_id)
            if not session:
                raise HTTPException(status_code=401, detail="Session không hợp lệ hoặc đã hết hạn")
            
            user_id = session['user_id']
            
            # Get user data
            user_result = self.supabase_admin.table('users').select("*").eq('id', user_id).execute()
            
            if not user_result.data:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
            
            user = user_result.data[0]
            
            # Check if user is active
            if not user.get('is_active'):
                raise HTTPException(status_code=401, detail="Tài khoản đã bị vô hiệu hóa")
            
            # Get wallet info
            wallet_result = self.supabase_admin.table('wallets').select("*").eq('user_id', user_id).execute()
            wallet = wallet_result.data[0] if wallet_result.data else {}
            
            # Extend session (refresh expiration)
            await self.extend_session(session_id)
            
            # Combine user and wallet data
            user_with_wallet = {**user, **wallet}
            
            return UserWithWallet(**user_with_wallet)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get current user error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi lấy thông tin người dùng")
    
    async def update_user(self, user_id: str, update_data: UserUpdate) -> User:
        """Update user profile"""
        try:
            # Prepare update data
            update_dict = {}
            if update_data.full_name is not None:
                update_dict['full_name'] = update_data.full_name
            if update_data.phone is not None:
                update_dict['phone'] = update_data.phone
            if update_data.avatar_url is not None:
                update_dict['avatar_url'] = update_data.avatar_url
            
            if not update_dict:
                raise HTTPException(status_code=400, detail="Không có dữ liệu để cập nhật")
            
            # Update user
            result = self.supabase.table('users').update(update_dict).eq('id', user_id).execute()
            
            if not result.data:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
            
            return User(**result.data[0])
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Update user error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi cập nhật thông tin")
    
    async def change_password(self, user_id: str, password_data: ChangePassword) -> Dict[str, str]:
        """Change user password"""
        try:
            # Get current user
            user_result = self.supabase.table('users').select("password_hash").eq('id', user_id).execute()
            
            if not user_result.data:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
            
            user = user_result.data[0]
            
            # Verify current password
            if not self.verify_password(password_data.current_password, user['password_hash']):
                raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
            
            # Hash new password
            new_hashed_password = self.hash_password(password_data.new_password)
            
            # Update password
            self.supabase.table('users').update({
                "password_hash": new_hashed_password
            }).eq('id', user_id).execute()
            
            return {"message": "Đổi mật khẩu thành công"}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Change password error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi đổi mật khẩu")

# Global auth manager
auth_manager = AuthManager()

# Dependency functions
async def get_current_user(
    request: Request,
    session_id: str = Cookie(None, alias=COOKIE_NAME)
) -> UserWithWallet:
    """FastAPI dependency to get current authenticated user from session cookie"""
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Không xác thực")
    
    return await auth_manager.get_current_user(session_id)

async def get_optional_user(
    request: Request,
    session_id: str = Cookie(None, alias=COOKIE_NAME)
) -> Optional[UserWithWallet]:
    """Get user if authenticated, otherwise return None - supports session cookies"""
    try:
        if session_id:
            return await auth_manager.get_current_user(session_id)
    except:
        pass
    return None

def require_admin(current_user: UserWithWallet = Depends(get_current_user)) -> UserWithWallet:
    """Require admin role"""
    try:
        supabase = get_supabase_client()
        
        # Check if user has admin role
        role_result = supabase.table('user_roles').select("roles(name)").eq('user_id', current_user.id).execute()
        
        user_roles = [role['roles']['name'] for role in role_result.data if role.get('roles')]
        
        if 'admin' not in user_roles and 'super_admin' not in user_roles:
            raise HTTPException(status_code=403, detail="Yêu cầu quyền admin")
        
        return current_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin check error: {e}")
        raise HTTPException(status_code=500, detail="Lỗi kiểm tra quyền admin")
