"""
Tạo đặc trưng cho mô hình ML/DL: Chỉ báo kỹ thuật, rolling stats, biến động, momentum
"""

import pandas as pd
import numpy as np
import ta

def add_technical_indicators_yf(df):
    """Tính toàn diện các chỉ báo PTKT cho dataframe giá"""
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)  # Drop the second level of MultiIndex
    df['Close'] = df['Close'].squeeze()  # Ensure 'close' is a Series
    # RSI
    df['rsi14'] = ta.momentum.RSIIndicator(df['Close'].squeeze(), window=14).rsi()
    # MACD
    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df['Close'])
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()
    # SMA, EMA
    df['sma20'] = ta.trend.SMAIndicator(df['Close'], 20).sma_indicator()
    df['ema20'] = ta.trend.EMAIndicator(df['Close'], 20).ema_indicator()
    # ATR
    df['atr14'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], 14).average_true_range()
    # Momentum
    df['mom10'] = ta.momentum.ROCIndicator(df['Close'], 10).roc()
    # Rolling volatility
    df['vol20'] = df['Close'].rolling(20).std()
    # Add all TA features
    df = ta.add_all_ta_features(df, open="Open", high="High", low="Low", close="Close", volume="Volume")
    return df

def add_technical_indicators_vnquant(df):
    """Tính toàn diện các chỉ báo PTKT cho dataframe giá"""
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)  # Drop the second level of MultiIndex
    df['close'] = df['close'].squeeze()  # Ensure 'close' is a Series
    # RSI
    df['rsi14'] = ta.momentum.RSIIndicator(df['close'].squeeze(), window=14).rsi()
    # MACD
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df['close'])
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()
    # SMA, EMA
    df['sma20'] = ta.trend.SMAIndicator(df['close'], 20).sma_indicator()
    df['ema20'] = ta.trend.EMAIndicator(df['close'], 20).ema_indicator()
    # ATR
    df['atr14'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], 14).average_true_range()
    # Momentum
    df['mom10'] = ta.momentum.ROCIndicator(df['close'], 10).roc()
    # Rolling volatility
    df['vol20'] = df['close'].rolling(20).std()
    # Add all TA features
    df = ta.add_all_ta_features(df, open="open", high="high", low="low", close="close", volume="volume_match")
    return df

def make_ml_features(df):
    """Tạo đặc trưng ML từ dữ liệu giá đã có chỉ báo kỹ thuật"""
    feats = ['rsi14', 'macd', 'macd_signal', 'bb_high', 'bb_low', 'sma20', 'ema20', 'atr14', 'mom10', 'vol20']
    return df[feats].dropna()

if __name__ == "__main__":
    from data_loader import load_stock_data_yf, load_stock_data_vn
    # df = load_stock_data_yf("VCB.VN", start="2023-01-01", end="2023-03-01", interval="1d")
    # df = add_technical_indicators_yf(df)
    df = load_stock_data_vn("VCB", start="2024-01-01", end="2030-06-18")
    df = add_technical_indicators_vnquant(df)

    # with open("columns.txt", "w") as f:
    #     for col in df.columns:
    #         f.write(f"{col}\n")

    print(df.iloc[1])
    # print(make_ml_features(df).tail())