#!/usr/bin/env python3
"""
Test script để kiểm tra logic VNQuant-first cho các chức năng fetch dữ liệu
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from data_loader import load_stock_data_vnquant, load_stock_data_yf
from portfolio_optimization import get_stock_data
from news_analysis import get_insights

def test_data_loader():
    """Test hàm load_stock_data_vnquant"""
    print("=== Testing load_stock_data_vnquant ===")
    
    # Test with Vietnamese stock
    print("Testing VCB (Vietnamese stock)...")
    try:
        df = load_stock_data_vnquant("VCB", asset_type='stock', start='2024-01-01', end='2024-12-31')
        if df is not None and not df.empty:
            print(f"✅ Successfully loaded VCB data: {len(df)} rows")
            print(f"Columns: {list(df.columns)}")
            print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
        else:
            print("❌ Failed to load VCB data")
    except Exception as e:
        print(f"❌ Error loading VCB: {e}")
    
    print()

def test_portfolio_optimization():
    """Test hàm get_stock_data trong portfolio optimization"""
    print("=== Testing Portfolio Optimization ===")
    
    try:
        symbols = ['VCB', 'BID']
        df_all = get_stock_data(symbols, 'stock', '2024-01-01', '2024-12-31')
        if df_all is not None and not df_all.empty:
            print(f"✅ Successfully loaded portfolio data: {len(df_all)} rows")
            print(f"Symbols: {list(df_all.columns)}")
        else:
            print("❌ Failed to load portfolio data")
    except Exception as e:
        print(f"❌ Error in portfolio optimization: {e}")
    
    print()

def test_news_analysis():
    """Test hàm get_insights trong news analysis"""
    print("=== Testing News Analysis ===")
    
    try:
        # This will test the data loading part of get_insights
        print("Testing insights for VCB...")
        # Note: This might take a while due to technical analysis
        result = get_insights("VCB", asset_type='stock', start_date='2024-01-01', look_back_days=7)
        if result:
            print("✅ Successfully generated insights")
            print(f"Result length: {len(str(result))}")
        else:
            print("❌ Failed to generate insights")
    except Exception as e:
        print(f"❌ Error in news analysis: {e}")
    
    print()

def test_crypto_fallback():
    """Test crypto vẫn sử dụng Yahoo Finance"""
    print("=== Testing Crypto Fallback ===")
    
    try:
        df = load_stock_data_vnquant("BTC", asset_type='crypto', start='2024-01-01', end='2024-12-31')
        if df is not None and not df.empty:
            print(f"✅ Successfully loaded BTC data: {len(df)} rows")
        else:
            print("❌ Failed to load BTC data")
    except Exception as e:
        print(f"❌ Error loading BTC: {e}")

if __name__ == "__main__":
    print("Testing VNQuant-first logic implementation...")
    print("=" * 50)
    
    test_data_loader()
    test_portfolio_optimization()
    # test_news_analysis()  # Comment out for now as it requires API keys
    test_crypto_fallback()
    
    print("=" * 50)
    print("Testing completed!")
