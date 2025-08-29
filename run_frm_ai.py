#!/usr/bin/env python3
"""
FRM-AI Application Launcher
Script khởi chạy ứng dụng FRM-AI với tất cả cấu hình
"""

import os
import sys
import logging
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# Setup paths
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Load environment variables
env_file = current_dir / '.env'
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded environment from {env_file}")
else:
    print(f"⚠️  Environment file not found: {env_file}")
    print("📝 Please copy .env.example to .env and configure your settings")

# Setup logging
def setup_logging():
    """Setup logging configuration"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_to_file = os.getenv('LOG_TO_FILE', 'True').lower() == 'true'
    log_file_path = os.getenv('LOG_FILE_PATH', 'logs/frm-ai.log')
    
    # Create logs directory if it doesn't exist
    if log_to_file:
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    
    # Configure logging
    handlers = [logging.StreamHandler()]
    if log_to_file:
        handlers.append(logging.FileHandler(log_file_path))
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    print(f"📊 Logging level: {log_level}")
    if log_to_file:
        print(f"📁 Log file: {log_file_path}")

def check_dependencies():
    """Check if all required dependencies are installed"""
    required_packages = [
        'fastapi',
        'uvicorn',
        'supabase',
        'pandas',
        'numpy',
        'yfinance',
        'ta',
        'pypfopt',
        'scikit-learn',
        'prophet',
        'pydantic',
        'python-jose',
        'passlib',
        'bcrypt'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n📦 Install missing packages with:")
        print("pip install -r requirements_fastapi.txt")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_environment():
    """Check environment configuration"""
    required_env_vars = [
        'SUPABASE_URL',
        'SUPABASE_ANON_KEY',
        'JWT_SECRET'
    ]
    
    missing_vars = []
    
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("⚠️  Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n📝 Please check your .env file configuration")
        return False
    
    print("✅ Environment configuration is valid")
    return True

def test_database_connection():
    """Test database connection"""
    try:
        from supabase_config import test_supabase_connection
        
        if test_supabase_connection():
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database connection failed")
            return False
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def main():
    """Main application launcher"""
    print("🚀 Starting FRM-AI Application...")
    print("=" * 50)
    
    # Setup logging
    setup_logging()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check environment
    if not check_environment():
        print("⚠️  Starting with incomplete configuration...")
    
    # Test database connection
    if not test_database_connection():
        print("⚠️  Starting without database connection...")
    
    # Get configuration from environment
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', '8000'))
    reload = os.getenv('RELOAD', 'True').lower() == 'true'
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    print(f"🌐 Server will start on: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"🔧 Debug mode: {'Enabled' if debug else 'Disabled'}")
    print(f"🔄 Auto-reload: {'Enabled' if reload else 'Disabled'}")
    print("=" * 50)
    
    try:
        # Start the server
        uvicorn.run(
            "app_fastapi:app",
            host=host,
            port=port,
            reload=reload,
            access_log=True,
            log_level="info" if debug else "warning"
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down FRM-AI gracefully...")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
