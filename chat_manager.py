"""
Chat Management System for FRM-AI
Hệ thống quản lý chat real-time
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import WebSocket, HTTPException
from supabase_config import get_supabase_client
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

# Pydantic Models
class ChatMessage(BaseModel):
    id: Optional[str] = None
    conversation_id: str
    sender_id: str
    content: str
    message_type: str = "text"  # text, image, file, system
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class Conversation(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    is_group: bool = False
    participant_ids: List[str]
    created_by: str
    created_at: Optional[datetime] = None
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None

class ChatParticipant(BaseModel):
    user_id: str
    conversation_id: str
    joined_at: datetime
    is_admin: bool = False
    is_active: bool = True

class TypingIndicator(BaseModel):
    conversation_id: str
    user_id: str
    user_name: str
    is_typing: bool

# Connection Manager
class ConnectionManager:
    def __init__(self):
        # Store active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Store user's current conversations
        self.user_conversations: Dict[str, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Add a new WebSocket connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        
        # Load user's conversations
        await self.load_user_conversations(user_id)
        
        logger.info(f"User {user_id} connected. Total connections: {len(self.active_connections[user_id])}")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                if user_id in self.user_conversations:
                    del self.user_conversations[user_id]
        
        logger.info(f"User {user_id} disconnected")
    
    async def load_user_conversations(self, user_id: str):
        """Load conversations for a user"""
        try:
            supabase = get_supabase_client()
            result = supabase.table("participants")\
                .select("conversation_id")\
                .eq("user_id", user_id)\
                .execute()
            
            conversation_ids = [item["conversation_id"] for item in result.data]
            self.user_conversations[user_id] = conversation_ids
            
        except Exception as e:
            logger.error(f"Error loading conversations for user {user_id}: {e}")
    
    async def send_personal_message(self, message: dict, user_id: str):
        """Send message to specific user"""
        if user_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {e}")
                    dead_connections.append(connection)
            
            # Remove dead connections
            for dead_conn in dead_connections:
                self.active_connections[user_id].remove(dead_conn)
    
    async def broadcast_to_conversation(self, message: dict, conversation_id: str, exclude_user: Optional[str] = None):
        """Broadcast message to all participants in a conversation"""
        try:
            supabase = get_supabase_client()
            
            # Get all participants
            participants = supabase.table("participants")\
                .select("user_id")\
                .eq("conversation_id", conversation_id)\
                .execute()
            
            for participant in participants.data:
                user_id = participant["user_id"]
                
                # Skip excluded user (usually the sender)
                if exclude_user and user_id == exclude_user:
                    continue
                
                await self.send_personal_message(message, user_id)
                
        except Exception as e:
            logger.error(f"Error broadcasting to conversation {conversation_id}: {e}")

# Chat Manager
class ChatManager:
    def __init__(self):
        # Use service key for chat operations to bypass RLS restrictions
        self.supabase = get_supabase_client(use_service_key=True)
        self.connection_manager = ConnectionManager()
    
    async def create_conversation(self, created_by: str, participant_ids: List[str], 
                                name: Optional[str] = None) -> Conversation:
        """Create a new conversation"""
        try:
            # Ensure creator is in participants
            all_participants = list(set([created_by] + participant_ids))
            
            conversation_data = {
                "name": name,
                "is_group": len(all_participants) > 2,
                "created_by": created_by,
                "created_at": datetime.now().isoformat()
            }
            
            # Insert conversation
            conversation_result = self.supabase.table("conversations")\
                .insert(conversation_data).execute()
            
            conversation_id = conversation_result.data[0]["id"]
            
            # Add participants
            participants_data = []
            for user_id in all_participants:
                participants_data.append({
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "joined_at": datetime.now().isoformat(),
                    "is_admin": user_id == created_by
                })
            
            self.supabase.table("participants").insert(participants_data).execute()
            
            # Create conversation object
            conversation = Conversation(
                id=conversation_id,
                name=name,
                is_group=len(all_participants) > 2,
                participant_ids=all_participants,
                created_by=created_by,
                created_at=datetime.fromisoformat(conversation_result.data[0]["created_at"])
            )
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")
    
    async def send_message(self, message: ChatMessage) -> ChatMessage:
        """Send a message in a conversation"""
        try:
            # Save message to database
            message_data = {
                "conversation_id": message.conversation_id,
                "sender_id": message.sender_id,
                "content": message.content,
                "message_type": message.message_type,
                "metadata": message.metadata,
                "created_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("messages").insert(message_data).execute()
            message_id = result.data[0]["id"]
            
            # Update conversation last message
            self.supabase.table("conversations")\
                .update({
                    "last_message": message.content[:100],  # Truncate for preview
                    "last_message_at": datetime.now().isoformat()
                })\
                .eq("id", message.conversation_id)\
                .execute()
            
            # Get sender info for broadcasting
            sender_info = self.supabase.table("users")\
                .select("full_name, email")\
                .eq("id", message.sender_id)\
                .execute()
            
            sender_name = "Unknown User"
            if sender_info.data:
                sender_name = sender_info.data[0].get("full_name") or sender_info.data[0].get("email")
            
            # Create message for broadcasting
            broadcast_message = {
                "type": "message",
                "data": {
                    "id": message_id,
                    "conversation_id": message.conversation_id,
                    "sender_id": message.sender_id,
                    "sender_name": sender_name,
                    "content": message.content,
                    "message_type": message.message_type,
                    "metadata": message.metadata,
                    "created_at": message_data["created_at"]
                }
            }
            
            # Broadcast to all participants except sender
            await self.connection_manager.broadcast_to_conversation(
                broadcast_message, 
                message.conversation_id, 
                exclude_user=message.sender_id
            )
            
            # Update message with ID and return
            message.id = message_id
            message.created_at = datetime.fromisoformat(message_data["created_at"])
            
            return message
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
    
    async def get_conversation_messages(self, conversation_id: str, user_id: str, 
                                      limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get messages for a conversation"""
        try:
            # Verify user is participant
            participant_check = self.supabase.table("participants")\
                .select("id")\
                .eq("conversation_id", conversation_id)\
                .eq("user_id", user_id)\
                .execute()
            
            if not participant_check.data:
                raise HTTPException(status_code=403, detail="Not authorized to view this conversation")
            
            # Get messages with sender info
            messages_result = self.supabase.table("messages")\
                .select("""
                    id, content, message_type, metadata, created_at, sender_id,
                    users!messages_sender_id_fkey(full_name, email, avatar_url)
                """)\
                .eq("conversation_id", conversation_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .offset(offset)\
                .execute()
            
            messages = []
            for msg in messages_result.data:
                sender_info = msg.get("users", {})
                messages.append({
                    "id": msg["id"],
                    "content": msg["content"],
                    "message_type": msg["message_type"],
                    "metadata": msg["metadata"],
                    "created_at": msg["created_at"],
                    "sender_id": msg["sender_id"],
                    "sender_name": sender_info.get("full_name") or sender_info.get("email", "Unknown"),
                    "sender_avatar": sender_info.get("avatar_url")
                })
            
            # Return in chronological order (oldest first)
            return list(reversed(messages))
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get messages: {str(e)}")
    
    async def get_user_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all conversations for a user"""
        try:
            result = self.supabase.table("participants")\
                .select("""
                    conversation_id,
                    conversations!participants_conversation_id_fkey(
                        id, name, is_group, created_at, last_message, last_message_at
                    )
                """)\
                .eq("user_id", user_id)\
                .eq("is_active", True)\
                .execute()
            
            conversations = []
            for item in result.data:
                conv = item["conversations"]
                if conv:  # Ensure conversation exists
                    conversations.append({
                        "id": conv["id"],
                        "name": conv["name"],
                        "is_group": conv["is_group"],
                        "created_at": conv["created_at"],
                        "last_message": conv["last_message"],
                        "last_message_at": conv["last_message_at"]
                    })
            
            # Sort by last message time
            conversations.sort(key=lambda x: x["last_message_at"] or x["created_at"], reverse=True)
            
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting user conversations: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get conversations: {str(e)}")
    
    async def handle_typing_indicator(self, user_id: str, conversation_id: str, 
                                    is_typing: bool, user_name: str):
        """Handle typing indicators"""
        typing_message = {
            "type": "typing",
            "data": {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "user_name": user_name,
                "is_typing": is_typing
            }
        }
        
        await self.connection_manager.broadcast_to_conversation(
            typing_message, conversation_id, exclude_user=user_id
        )

# Global chat manager instance
chat_manager = ChatManager()

