"""
Supabase Configuration and Client Setup
Cấu hình và thiết lập client Supabase
"""

import os
from supabase import create_client, Client
from typing import Optional
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

def get_supabase_client(use_service_key: bool = False) -> Client:
    """Get Supabase client with option to use service key"""
    try:
        # Supabase configuration
        url = os.getenv("SUPABASE_URL")
        anon_key = os.getenv("SUPABASE_ANON_KEY")
        service_key = os.getenv("SUPABASE_SERVICE_KEY")

        key = service_key if use_service_key else anon_key

        client = create_client(url, key)
        logger.info(f"Supabase client initialized successfully {'with service key' if use_service_key else 'with anon key'}")
        return client
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        raise

async def test_supabase_connection(client: Client = None) -> bool:
    """Test Supabase connection"""
    try:
        if client is None:
            client = get_supabase_client()
        
        # Test connection với bảng users
        result = client.table("users").select("id").limit(1).execute()
        logger.info("✅ Supabase connection successful")
        return True
    except Exception as e:
        logger.error(f"Supabase connection test failed: {e}")
        return False