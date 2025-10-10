#!/usr/bin/env python3
"""
Cache Management Utility
Tiện ích quản lý cache Redis cho FRM-AI
"""

import os
import sys
import argparse
import json
from datetime import datetime, timedelta

# Add backend directory to path
sys.path.append(os.path.dirname(__file__))

from redis_config import get_redis_manager
from stock_cache_manager import get_cache_manager

def status():
    """Show cache status"""
    print("📊 Cache System Status")
    print("=" * 50)
    
    try:
        # Redis connection
        redis_manager = get_redis_manager()
        if redis_manager.is_connected():
            print("✅ Redis: Connected")
        else:
            print("❌ Redis: Disconnected")
            return
        
        # Cache manager status
        cache_manager = get_cache_manager()
        status = cache_manager.get_cache_status()
        
        print(f"📦 Cached symbols: {status.get('cached_symbols_count', 0)}")
        print(f"💾 Memory used: {status.get('memory_used', 'N/A')}")
        print(f"⏰ Last full fetch: {status.get('last_full_fetch', 'Never')}")
        print(f"🔧 Scheduler running: {status.get('scheduler_running', False)}")
        print(f"⏭️  Next full fetch: {status.get('next_full_fetch', 'Not scheduled')}")
        
        # Show some cached symbols
        cached_symbols = status.get('cached_symbols', [])
        if cached_symbols:
            print(f"\n🔤 Sample cached symbols: {', '.join(cached_symbols)}")
        
    except Exception as e:
        print(f"❌ Error getting status: {e}")

def list_symbols():
    """List all cached symbols"""
    try:
        redis_manager = get_redis_manager()
        symbols = redis_manager.get_cached_symbols()
        
        print(f"📦 Total cached symbols: {len(symbols)}")
        print("=" * 50)
        
        # Group by type (basic heuristic)
        vn_stocks = [s for s in symbols if len(s) == 3 and s.isalpha()]
        crypto = [s for s in symbols if len(s) <= 5 and s not in vn_stocks]
        others = [s for s in symbols if s not in vn_stocks and s not in crypto]
        
        if vn_stocks:
            print(f"\n🇻🇳 Vietnamese Stocks ({len(vn_stocks)}):")
            for i, symbol in enumerate(sorted(vn_stocks)):
                if i % 10 == 0:
                    print()
                print(f"{symbol:4}", end=" ")
            print()
        
        if crypto:
            print(f"\n💰 Cryptocurrencies ({len(crypto)}):")
            for i, symbol in enumerate(sorted(crypto)):
                if i % 10 == 0:
                    print()
                print(f"{symbol:5}", end=" ")
            print()
        
        if others:
            print(f"\n🌐 Others ({len(others)}):")
            for symbol in sorted(others):
                print(f"  {symbol}")
        
    except Exception as e:
        print(f"❌ Error listing symbols: {e}")

def check_symbol(symbol):
    """Check specific symbol cache"""
    try:
        redis_manager = get_redis_manager()
        
        print(f"🔍 Checking symbol: {symbol.upper()}")
        print("=" * 50)
        
        is_cached = redis_manager.is_symbol_cached(symbol)
        print(f"📦 Cached: {'✅ Yes' if is_cached else '❌ No'}")
        
        if is_cached:
            data = redis_manager.get_stock_data(symbol)
            if data:
                print(f"📊 Asset type: {data.get('asset_type', 'Unknown')}")
                print(f"📈 Data points: {data.get('data_points', 0)}")
                print(f"⏰ Last updated: {data.get('last_updated', 'Unknown')}")
                
                # Show data range
                records = data.get('data', [])
                if records:
                    dates = [r.get('Date') for r in records if r.get('Date')]
                    if dates:
                        print(f"📅 Date range: {min(dates)} to {max(dates)}")
        
    except Exception as e:
        print(f"❌ Error checking symbol: {e}")

def refresh_cache():
    """Trigger manual cache refresh"""
    print("🔄 Triggering manual cache refresh...")
    print("⚠️  This will take several minutes...")
    
    try:
        cache_manager = get_cache_manager()
        cache_manager.daily_full_fetch()
        print("✅ Cache refresh completed!")
        
    except Exception as e:
        print(f"❌ Error refreshing cache: {e}")

def clear_cache():
    """Clear all cache"""
    print("🗑️  Clearing all cache data...")
    
    try:
        redis_manager = get_redis_manager()
        redis_manager.clear_cache()
        print("✅ Cache cleared successfully!")
        
    except Exception as e:
        print(f"❌ Error clearing cache: {e}")

def test_fetch(symbol, asset_type="stock"):
    """Test fetching a specific symbol"""
    print(f"🧪 Testing fetch for {symbol} ({asset_type})...")
    
    try:
        cache_manager = get_cache_manager()
        data = cache_manager.get_stock_data(symbol, asset_type)
        
        if data:
            print(f"✅ Successfully fetched {symbol}")
            print(f"📊 Data points: {data.get('data_points', 0)}")
            print(f"📈 Asset type: {data.get('asset_type', 'Unknown')}")
        else:
            print(f"❌ Failed to fetch {symbol}")
        
    except Exception as e:
        print(f"❌ Error testing fetch: {e}")

def export_cache(filename):
    """Export cache data to JSON file"""
    print(f"📤 Exporting cache data to {filename}...")
    
    try:
        redis_manager = get_redis_manager()
        symbols = redis_manager.get_cached_symbols()
        
        export_data = {
            "export_time": datetime.now().isoformat(),
            "total_symbols": len(symbols),
            "symbols": {}
        }
        
        for symbol in symbols:
            data = redis_manager.get_stock_data(symbol)
            if data:
                # Remove actual data to keep file size manageable
                export_data["symbols"][symbol] = {
                    "asset_type": data.get("asset_type"),
                    "data_points": data.get("data_points"),
                    "last_updated": data.get("last_updated")
                }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"✅ Exported {len(symbols)} symbols to {filename}")
        
    except Exception as e:
        print(f"❌ Error exporting cache: {e}")

def scheduler_info():
    """Show scheduler information"""
    print("📅 Scheduler Information")
    print("=" * 50)
    
    try:
        cache_manager = get_cache_manager()
        
        print(f"🔧 Running: {cache_manager.is_running}")
        
        if cache_manager.is_running:
            jobs = cache_manager.scheduler.get_jobs()
            print(f"📋 Total jobs: {len(jobs)}")
            
            for job in jobs:
                print(f"\n📌 {job.name}")
                print(f"   ID: {job.id}")
                print(f"   Next run: {job.next_run_time}")
                print(f"   Trigger: {job.trigger}")
        else:
            print("⚠️  Scheduler is not running")
            
    except Exception as e:
        print(f"❌ Error getting scheduler info: {e}")

def main():
    parser = argparse.ArgumentParser(description="FRM-AI Cache Management Utility")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    subparsers.add_parser('status', help='Show cache status')
    
    # List symbols command
    subparsers.add_parser('list', help='List all cached symbols')
    
    # Check symbol command
    check_parser = subparsers.add_parser('check', help='Check specific symbol')
    check_parser.add_argument('symbol', help='Symbol to check')
    
    # Refresh command
    subparsers.add_parser('refresh', help='Trigger manual cache refresh')
    
    # Clear command
    subparsers.add_parser('clear', help='Clear all cache data')
    
    # Test fetch command
    test_parser = subparsers.add_parser('test', help='Test fetching a symbol')
    test_parser.add_argument('symbol', help='Symbol to test')
    test_parser.add_argument('--type', default='stock', choices=['stock', 'crypto'], help='Asset type')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export cache data')
    export_parser.add_argument('filename', help='Output filename')
    
    # Scheduler command
    subparsers.add_parser('scheduler', help='Show scheduler information')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute commands
    if args.command == 'status':
        status()
    elif args.command == 'list':
        list_symbols()
    elif args.command == 'check':
        check_symbol(args.symbol)
    elif args.command == 'refresh':
        refresh_cache()
    elif args.command == 'clear':
        clear_cache()
    elif args.command == 'test':
        test_fetch(args.symbol, args.type)
    elif args.command == 'export':
        export_cache(args.filename)
    elif args.command == 'scheduler':
        scheduler_info()

if __name__ == "__main__":
    main()
