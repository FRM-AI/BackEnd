"""
Social Media Features Management System
Hệ thống quản lý tính năng mạng xã hội
"""

from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid
import logging
from supabase_config import get_supabase_client

logger = logging.getLogger(__name__)

# Pydantic Models for Social Features
class UserProfile(BaseModel):
    user_id: str
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    created_at: datetime
    updated_at: datetime

class UserProfileUpdate(BaseModel):
    bio: Optional[str] = Field(None, max_length=500, description="Tiểu sử cá nhân")
    profile_picture_url: Optional[str] = Field(None, description="URL ảnh đại diện")

class UserProfileInfo(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    is_following: bool = False
    created_at: datetime

class FollowInfo(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    followed_at: datetime

class PostCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200, description="Tiêu đề bài viết")
    content: List[Dict[str, Any]] = Field(..., description="Nội dung bài viết (JSON format)")
    tags: List[str] = Field(default=[], description="Tags cho bài viết")

class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    content: Optional[List[Dict[str, Any]]] = None
    tags: Optional[List[str]] = None

class Post(BaseModel):
    id: str
    user_id: str
    title: str
    content: List[Dict[str, Any]]
    tags: List[str]
    likes_count: int = 0
    comments_count: int = 0
    created_at: datetime
    updated_at: datetime
    # User info
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None
    is_liked: bool = False

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000, description="Nội dung bình luận")

class Comment(BaseModel):
    id: str
    post_id: str
    user_id: str
    content: str
    created_at: datetime
    # User info
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None

# Social Manager Class
class SocialManager:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.supabase_admin = get_supabase_client(use_service_key=True)

    # ================================
    # USER PROFILE MANAGEMENT
    # ================================

    async def get_user_profile(self, user_id: str, current_user_id: Optional[str] = None) -> UserProfileInfo:
        """Lấy thông tin hồ sơ người dùng"""
        try:
            # Get user basic info
            user_result = self.supabase.table('users').select(
                "id, email, full_name, avatar_url, created_at"
            ).eq('id', user_id).execute()

            if not user_result.data:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

            user_data = user_result.data[0]

            # Get profile extended info
            profile_result = self.supabase.table('user_profiles').select(
                "bio, profile_picture_url, followers_count, following_count"
            ).eq('user_id', user_id).execute()

            profile_data = profile_result.data[0] if profile_result.data else {}

            # Check if current user is following this user
            is_following = False
            if current_user_id and current_user_id != user_id:
                follow_result = self.supabase.table('follows').select("follower_id").eq(
                    'follower_id', current_user_id
                ).eq('following_id', user_id).execute()
                is_following = len(follow_result.data) > 0

            # Combine data
            combined_data = {
                **user_data,
                **profile_data,
                "user_id": user_data["id"],
                "is_following": is_following
            }

            return UserProfileInfo(**combined_data)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get user profile error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi lấy hồ sơ người dùng")

    async def update_user_profile(self, user_id: str, profile_data: UserProfileUpdate) -> UserProfile:
        """Cập nhật hồ sơ cá nhân"""
        try:
            # Prepare update data
            update_dict = {}
            if profile_data.bio is not None:
                update_dict['bio'] = profile_data.bio
            if profile_data.profile_picture_url is not None:
                update_dict['profile_picture_url'] = profile_data.profile_picture_url

            if not update_dict:
                raise HTTPException(status_code=400, detail="Không có dữ liệu để cập nhật")

            # Check if profile exists
            existing_result = self.supabase.table('user_profiles').select("user_id").eq('user_id', user_id).execute()

            if existing_result.data:
                # Update existing profile
                result = self.supabase.table('user_profiles').update(update_dict).eq('user_id', user_id).execute()
            else:
                # Create new profile
                update_dict['user_id'] = user_id
                result = self.supabase.table('user_profiles').insert(update_dict).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể cập nhật hồ sơ")

            return UserProfile(**result.data[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Update profile error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi cập nhật hồ sơ")

    async def get_followers(self, user_id: str, limit: int = 50, offset: int = 0) -> List[FollowInfo]:
        """Lấy danh sách người theo dõi"""
        try:
            result = self.supabase.table('follows').select(
                "follower_id, followed_at, users!follows_follower_id_fkey(id, email, full_name, avatar_url)"
            ).eq('following_id', user_id).order('followed_at', desc=True).range(offset, offset + limit - 1).execute()

            followers = []
            for follow in result.data:
                user_info = follow['users']
                followers.append(FollowInfo(
                    user_id=user_info['id'],
                    email=user_info['email'],
                    full_name=user_info['full_name'],
                    avatar_url=user_info['avatar_url'],
                    followed_at=datetime.fromisoformat(follow['followed_at'].replace('Z', '+00:00'))
                ))

            return followers

        except Exception as e:
            logger.error(f"Get followers error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi lấy danh sách người theo dõi")

    async def get_following(self, user_id: str, limit: int = 50, offset: int = 0) -> List[FollowInfo]:
        """Lấy danh sách người đang theo dõi"""
        try:
            result = self.supabase.table('follows').select(
                "following_id, followed_at, users!follows_following_id_fkey(id, email, full_name, avatar_url)"
            ).eq('follower_id', user_id).order('followed_at', desc=True).range(offset, offset + limit - 1).execute()

            following = []
            for follow in result.data:
                user_info = follow['users']
                following.append(FollowInfo(
                    user_id=user_info['id'],
                    email=user_info['email'],
                    full_name=user_info['full_name'],
                    avatar_url=user_info['avatar_url'],
                    followed_at=datetime.fromisoformat(follow['followed_at'].replace('Z', '+00:00'))
                ))

            return following

        except Exception as e:
            logger.error(f"Get following error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi lấy danh sách người đang theo dõi")

    async def follow_user(self, follower_id: str, following_id: str) -> Dict[str, str]:
        """Theo dõi người dùng khác"""
        try:
            if follower_id == following_id:
                raise HTTPException(status_code=400, detail="Không thể tự theo dõi bản thân")

            # Check if already following
            existing = self.supabase.table('follows').select("follower_id").eq(
                'follower_id', follower_id
            ).eq('following_id', following_id).execute()

            if existing.data:
                raise HTTPException(status_code=400, detail="Đã theo dõi người dùng này rồi")

            # Check if target user exists
            user_exists = self.supabase.table('users').select("id").eq('id', following_id).execute()
            if not user_exists.data:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

            # Create follow relationship
            self.supabase.table('follows').insert({
                "follower_id": follower_id,
                "following_id": following_id
            }).execute()

            # Update counts
            await self._update_follow_counts(following_id, follower_id)

            return {"message": "Đã theo dõi thành công"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Follow user error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi theo dõi người dùng")

    async def unfollow_user(self, follower_id: str, following_id: str) -> Dict[str, str]:
        """Bỏ theo dõi người dùng khác"""
        try:
            # Check if actually following
            existing = self.supabase.table('follows').select("follower_id").eq(
                'follower_id', follower_id
            ).eq('following_id', following_id).execute()

            if not existing.data:
                raise HTTPException(status_code=400, detail="Không theo dõi người dùng này")

            # Remove follow relationship
            self.supabase.table('follows').delete().eq(
                'follower_id', follower_id
            ).eq('following_id', following_id).execute()

            # Update counts
            await self._update_follow_counts(following_id, follower_id)

            return {"message": "Đã bỏ theo dõi thành công"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unfollow user error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi bỏ theo dõi người dùng")

    async def _update_follow_counts(self, following_id: str, follower_id: str):
        """Cập nhật số lượng người theo dõi và đang theo dõi"""
        try:
            # Update followers count for the followed user
            followers_count = self.supabase.table('follows').select(
                "follower_id", count="exact"
            ).eq('following_id', following_id).execute()

            # Update following count for the follower
            following_count = self.supabase.table('follows').select(
                "following_id", count="exact"
            ).eq('follower_id', follower_id).execute()

            # Update user_profiles table
            for user_id, count, field in [
                (following_id, followers_count.count, 'followers_count'),
                (follower_id, following_count.count, 'following_count')
            ]:
                # Check if profile exists
                profile_exists = self.supabase.table('user_profiles').select("user_id").eq('user_id', user_id).execute()
                
                if profile_exists.data:
                    self.supabase.table('user_profiles').update({field: count}).eq('user_id', user_id).execute()
                else:
                    self.supabase.table('user_profiles').insert({
                        'user_id': user_id,
                        field: count
                    }).execute()

        except Exception as e:
            logger.error(f"Update follow counts error: {e}")

    # ================================
    # POST MANAGEMENT
    # ================================

    async def create_post(self, user_id: str, post_data: PostCreate) -> Post:
        """Tạo bài viết mới"""
        try:
            # Create post
            insert_data = {
                "user_id": user_id,
                "title": post_data.title,
                "content": post_data.content,
                "tags": post_data.tags
            }

            result = self.supabase.table('posts').insert(insert_data).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể tạo bài viết")

            post = result.data[0]

            # Get user info for response
            user_result = self.supabase.table('users').select(
                "full_name, avatar_url"
            ).eq('id', user_id).execute()

            user_info = user_result.data[0] if user_result.data else {}

            # Combine data
            post_data = {
                **post,
                "author_name": user_info.get('full_name'),
                "author_avatar": user_info.get('avatar_url'),
                "is_liked": False
            }

            return Post(**post_data)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Create post error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi tạo bài viết")

    async def get_posts(
        self, 
        user_id: Optional[str] = None, 
        tags: Optional[List[str]] = None,
        limit: int = 20, 
        offset: int = 0,
        current_user_id: Optional[str] = None
    ) -> List[Post]:
        """Lấy danh sách bài viết với các bộ lọc"""
        try:
            # Build query
            query = self.supabase.table('posts').select(
                "*, users!posts_user_id_fkey(full_name, avatar_url)"
            )

            # Apply filters
            if user_id:
                query = query.eq('user_id', user_id)
            
            if tags:
                # Filter by tags (contains any of the specified tags)
                for tag in tags:
                    query = query.contains('tags', [tag])

            # Execute query with pagination
            result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()

            posts = []
            for post in result.data:
                user_info = post['users']
                
                # Check if current user liked this post
                is_liked = False
                if current_user_id:
                    # This would require a likes table - for now set to False
                    # You might want to implement post likes functionality later
                    is_liked = False

                post_data = {
                    **{k: v for k, v in post.items() if k != 'users'},
                    "author_name": user_info.get('full_name') if user_info else None,
                    "author_avatar": user_info.get('avatar_url') if user_info else None,
                    "is_liked": is_liked
                }

                posts.append(Post(**post_data))

            return posts

        except Exception as e:
            logger.error(f"Get posts error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi lấy danh sách bài viết")

    async def get_post(self, post_id: str, current_user_id: Optional[str] = None) -> Post:
        """Lấy chi tiết bài viết"""
        try:
            result = self.supabase.table('posts').select(
                "*, users!posts_user_id_fkey(full_name, avatar_url)"
            ).eq('id', post_id).execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Bài viết không tồn tại")

            post = result.data[0]
            user_info = post['users']

            # Check if current user liked this post
            is_liked = False
            if current_user_id:
                # Implement like checking logic here if needed
                is_liked = False

            post_data = {
                **{k: v for k, v in post.items() if k != 'users'},
                "author_name": user_info.get('full_name') if user_info else None,
                "author_avatar": user_info.get('avatar_url') if user_info else None,
                "is_liked": is_liked
            }

            return Post(**post_data)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get post error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi lấy bài viết")

    async def update_post(self, post_id: str, user_id: str, update_data: PostUpdate) -> Post:
        """Cập nhật bài viết"""
        try:
            # Check if post exists and belongs to user
            existing_result = self.supabase.table('posts').select("user_id").eq('id', post_id).execute()

            if not existing_result.data:
                raise HTTPException(status_code=404, detail="Bài viết không tồn tại")

            if existing_result.data[0]['user_id'] != user_id:
                raise HTTPException(status_code=403, detail="Không có quyền chỉnh sửa bài viết này")

            # Prepare update data
            update_dict = {}
            if update_data.title is not None:
                update_dict['title'] = update_data.title
            if update_data.content is not None:
                update_dict['content'] = update_data.content
            if update_data.tags is not None:
                update_dict['tags'] = update_data.tags

            if not update_dict:
                raise HTTPException(status_code=400, detail="Không có dữ liệu để cập nhật")

            # Update post
            result = self.supabase.table('posts').update(update_dict).eq('id', post_id).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể cập nhật bài viết")

            return await self.get_post(post_id, user_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Update post error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi cập nhật bài viết")

    async def delete_post(self, post_id: str, user_id: str) -> Dict[str, str]:
        """Xóa bài viết"""
        try:
            # Check if post exists and belongs to user
            existing_result = self.supabase.table('posts').select("user_id").eq('id', post_id).execute()

            if not existing_result.data:
                raise HTTPException(status_code=404, detail="Bài viết không tồn tại")

            if existing_result.data[0]['user_id'] != user_id:
                raise HTTPException(status_code=403, detail="Không có quyền xóa bài viết này")

            # Delete post (cascading will delete comments)
            self.supabase.table('posts').delete().eq('id', post_id).execute()

            return {"message": "Đã xóa bài viết thành công"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Delete post error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi xóa bài viết")

    # ================================
    # COMMENT MANAGEMENT
    # ================================

    async def create_comment(self, post_id: str, user_id: str, comment_data: CommentCreate) -> Comment:
        """Tạo bình luận mới"""
        try:
            # Check if post exists
            post_result = self.supabase.table('posts').select("id").eq('id', post_id).execute()
            if not post_result.data:
                raise HTTPException(status_code=404, detail="Bài viết không tồn tại")

            # Create comment
            insert_data = {
                "post_id": post_id,
                "user_id": user_id,
                "content": comment_data.content
            }

            result = self.supabase.table('comments').insert(insert_data).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Không thể tạo bình luận")

            comment = result.data[0]

            # Update comments count
            await self._update_comments_count(post_id)

            # Get user info for response
            user_result = self.supabase.table('users').select(
                "full_name, avatar_url"
            ).eq('id', user_id).execute()

            user_info = user_result.data[0] if user_result.data else {}

            # Combine data
            comment_data = {
                **comment,
                "author_name": user_info.get('full_name'),
                "author_avatar": user_info.get('avatar_url')
            }

            return Comment(**comment_data)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Create comment error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi tạo bình luận")

    async def get_comments(self, post_id: str, limit: int = 50, offset: int = 0) -> List[Comment]:
        """Lấy danh sách bình luận của bài viết"""
        try:
            result = self.supabase.table('comments').select(
                "*, users!comments_user_id_fkey(full_name, avatar_url)"
            ).eq('post_id', post_id).order('created_at', desc=True).range(offset, offset + limit - 1).execute()

            comments = []
            for comment in result.data:
                user_info = comment['users']
                
                comment_data = {
                    **{k: v for k, v in comment.items() if k != 'users'},
                    "author_name": user_info.get('full_name') if user_info else None,
                    "author_avatar": user_info.get('avatar_url') if user_info else None
                }

                comments.append(Comment(**comment_data))

            return comments

        except Exception as e:
            logger.error(f"Get comments error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi lấy danh sách bình luận")

    async def delete_comment(self, comment_id: str, user_id: str) -> Dict[str, str]:
        """Xóa bình luận"""
        try:
            # Check if comment exists and belongs to user
            existing_result = self.supabase.table('comments').select("user_id, post_id").eq('id', comment_id).execute()

            if not existing_result.data:
                raise HTTPException(status_code=404, detail="Bình luận không tồn tại")

            comment_data = existing_result.data[0]
            if comment_data['user_id'] != user_id:
                raise HTTPException(status_code=403, detail="Không có quyền xóa bình luận này")

            # Delete comment
            self.supabase.table('comments').delete().eq('id', comment_id).execute()

            # Update comments count
            await self._update_comments_count(comment_data['post_id'])

            return {"message": "Đã xóa bình luận thành công"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Delete comment error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi xóa bình luận")

    async def _update_comments_count(self, post_id: str):
        """Cập nhật số lượng bình luận của bài viết"""
        try:
            count_result = self.supabase.table('comments').select("id", count="exact").eq('post_id', post_id).execute()
            comments_count = count_result.count or 0

            self.supabase.table('posts').update({
                'comments_count': comments_count
            }).eq('id', post_id).execute()

        except Exception as e:
            logger.error(f"Update comments count error: {e}")

    # ================================
    # LIKE FUNCTIONALITY (Optional - can be implemented later)
    # ================================

    async def like_post(self, post_id: str, user_id: str) -> Dict[str, str]:
        """Thích bài viết (placeholder - cần tạo bảng post_likes)"""
        # This would require a post_likes table
        # For now, we'll just increment the likes_count
        try:
            # Check if post exists
            post_result = self.supabase.table('posts').select("id, likes_count").eq('id', post_id).execute()
            if not post_result.data:
                raise HTTPException(status_code=404, detail="Bài viết không tồn tại")

            # For now, just increment the count
            # In a real implementation, you'd check if user already liked and store in post_likes table
            current_likes = post_result.data[0]['likes_count']
            self.supabase.table('posts').update({
                'likes_count': current_likes + 1
            }).eq('id', post_id).execute()

            return {"message": "Đã thích bài viết"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Like post error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi thích bài viết")

    async def unlike_post(self, post_id: str, user_id: str) -> Dict[str, str]:
        """Bỏ thích bài viết (placeholder)"""
        try:
            # Check if post exists
            post_result = self.supabase.table('posts').select("id, likes_count").eq('id', post_id).execute()
            if not post_result.data:
                raise HTTPException(status_code=404, detail="Bài viết không tồn tại")

            # For now, just decrement the count (with minimum of 0)
            current_likes = post_result.data[0]['likes_count']
            new_likes = max(0, current_likes - 1)
            
            self.supabase.table('posts').update({
                'likes_count': new_likes
            }).eq('id', post_id).execute()

            return {"message": "Đã bỏ thích bài viết"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unlike post error: {e}")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi bỏ thích bài viết")

# Global social manager instance
social_manager = SocialManager()
