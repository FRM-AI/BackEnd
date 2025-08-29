import pandas as pd
import numpy as np
from data_loader import *
from feature_engineering import *
from alert import send_alert

def calculate_dynamic_thresholds(df, indicator, window=20, multiplier=1.5):
    """Calculate adaptive thresholds based on historical volatility"""
    mean = df[indicator].rolling(window=window).mean()
    std = df[indicator].rolling(window=window).std()
    upper = mean + multiplier * std
    lower = mean - multiplier * std
    return upper, lower

def detect_signals(df):
    """Detect signals using all technical indicators from columns.txt"""
    signals = []
    last = df.iloc[-1]  # Most recent data
    prev = df.iloc[-2]  # Previous data

    # Momentum Indicators
    rsi_upper, rsi_lower = calculate_dynamic_thresholds(df, 'momentum_rsi')
    
    if last['momentum_rsi'] < rsi_lower.iloc[-1]:
        signals.append(f"RSI Oversold ({last['momentum_rsi']:.2f} < {rsi_lower.iloc[-1]:.2f})")
    if last['momentum_rsi'] > rsi_upper.iloc[-1]:
        signals.append(f"RSI Overbought ({last['momentum_rsi']:.2f} > {rsi_upper.iloc[-1]:.2f})")

    if last['momentum_stoch_rsi_k'] < 20 and last['momentum_stoch_rsi_d'] < 20:
        signals.append(f"Stochastic RSI Oversold (K = {last['momentum_stoch_rsi_k']:.2f} < 20, D = {last['momentum_stoch_rsi_d']:.2f} < 20)")
    if last['momentum_stoch_rsi_k'] > 80 and last['momentum_stoch_rsi_d'] > 80:
        signals.append(f"Stochastic RSI Overbought (K = {last['momentum_stoch_rsi_k']:.2f} > 80, D = {last['momentum_stoch_rsi_d']:.2f} > 80)")

    if last['trend_cci'] < -100:
        signals.append(f"CCI Oversold ({last['trend_cci']:.2f} < -100)")
    if last['trend_cci'] > 100:
        signals.append(f"CCI Overbought ({last['trend_cci']:.2f} > 100)")

    if last['momentum_tsi'] < -25:
        signals.append(f"TSI Oversold ({last['momentum_tsi']:.2f} < -25)")
    if last['momentum_tsi'] > 25:
        signals.append(f"TSI Overbought ({last['momentum_tsi']:.2f} > 25)")

    if last['momentum_uo'] < 30:
        signals.append(f"Ultimate Oscillator Oversold ({last['momentum_uo']:.2f} < 30)")
    if last['momentum_uo'] > 70:
        signals.append(f"Ultimate Oscillator Overbought ({last['momentum_uo']:.2f} > 70)")

    if last['momentum_stoch'] < 20:
        signals.append(f"Stochastic Oversold ({last['momentum_stoch']:.2f} < 20)")
    if last['momentum_stoch'] > 80:
        signals.append(f"Stochastic Overbought ({last['momentum_stoch']:.2f} > 80)")

    if last['momentum_wr'] < -80:
        signals.append(f"Williams %R Oversold ({last['momentum_wr']:.2f} < -80)")
    if last['momentum_wr'] > -20:
        signals.append(f"Williams %R Overbought ({last['momentum_wr']:.2f} > -20)")

    if last['momentum_ao'] > 0 and prev['momentum_ao'] < 0:
        signals.append(f"Awesome Oscillator Bullish Crossover (Last AO = {last['momentum_ao']:.2f} > 0, Previous AO = {prev['momentum_ao']:.2f} < 0)")
    if last['momentum_ao'] < 0 and prev['momentum_ao'] > 0:
        signals.append(f"Awesome Oscillator Bearish Crossover (Last AO = {last['momentum_ao']:.2f} < 0, Previous AO = {prev['momentum_ao']:.2f} > 0)")

    if last['momentum_roc'] > 5:
        signals.append(f"ROC Bullish ({last['momentum_roc']:.2f} > 5)")
    if last['momentum_roc'] < -5:
        signals.append(f"ROC Bearish ({last['momentum_roc']:.2f} < -5)")

    if last['momentum_ppo'] > last['momentum_ppo_signal']:
        signals.append("PPO Bullish Crossover")
    if last['momentum_ppo'] < last['momentum_ppo_signal']:
        signals.append("PPO Bearish Crossover")

    # Trend Indicators
    if prev['trend_macd'] < prev['trend_macd_signal'] and last['trend_macd'] > last['trend_macd_signal']:
        signals.append("MACD Bullish Crossover")
    if prev['trend_macd'] > prev['trend_macd_signal'] and last['trend_macd'] < last['trend_macd_signal']:
        signals.append("MACD Bearish Crossover")

    if last['Close'] > last['trend_ichimoku_a'] and last['trend_ichimoku_a'] > last['trend_ichimoku_b']:
        signals.append("Ichimoku Bullish (Price above Cloud)")
    if last['Close'] < last['trend_ichimoku_a'] and last['trend_ichimoku_a'] < last['trend_ichimoku_b']:
        signals.append("Ichimoku Bearish (Price below Cloud)")

    if last['trend_adx'] > 25 and last['trend_adx_pos'] > last['trend_adx_neg']:
        signals.append(f"Strong Bullish Trend (ADX = {last['trend_adx']:.2f} > 25, +DI = {last['trend_adx_pos']:.2f} > -DI = {last['trend_adx_neg']:.2f})")
    if last['trend_adx'] > 25 and last['trend_adx_neg'] > last['trend_adx_pos']:
        signals.append(f"Strong Bearish Trend (ADX = {last['trend_adx']:.2f} > 25, +DI = {last['trend_adx_pos']:.2f} < -DI = {last['trend_adx_neg']:.2f})")

    if last['trend_vortex_ind_pos'] > last['trend_vortex_ind_neg']:
        signals.append("Vortex Indicator Bullish")
    if last['trend_vortex_ind_neg'] > last['trend_vortex_ind_pos']:
        signals.append("Vortex Indicator Bearish")

    if last['trend_trix'] > 0 and prev['trend_trix'] < 0:
        signals.append("TRIX Bullish Crossover")
    if last['trend_trix'] < 0 and prev['trend_trix'] > 0:
        signals.append("TRIX Bearish Crossover")

    if last['trend_mass_index'] > 27:
        signals.append(f"Mass Index Reversal Signal ({last['trend_mass_index']:.2f} > 27)")

    if last['trend_kst'] > last['trend_kst_sig']:
        signals.append("KST Bullish Crossover")
    if last['trend_kst'] < last['trend_kst_sig']:
        signals.append("KST Bearish Crossover")

    if last['trend_psar_up_indicator'] == 1:
        signals.append("PSAR Bullish Reversal")
    if last['trend_psar_down_indicator'] == 1:
        signals.append("PSAR Bearish Reversal")

    if last['Close'] > last['trend_sma_fast'] and last['trend_sma_fast'] > last['trend_sma_slow']:
        signals.append(f"SMA Fast = {last['trend_sma_fast']:.2f} > Slow Bullish = {last['trend_sma_slow']:.2f}")
    if last['Close'] < last['trend_sma_fast'] and last['trend_sma_fast'] < last['trend_sma_slow']:
        signals.append(f"SMA Fast = {last['trend_sma_fast']:.2f} < Slow Bearish = {last['trend_sma_slow']:.2f}")

    if last['Close'] > last['trend_ema_fast'] and last['trend_ema_fast'] > last['trend_ema_slow']:
        signals.append(f"EMA Fast = {last['trend_ema_fast']:.2f} > Slow Bullish = {last['trend_ema_slow']:.2f}")
    if last['Close'] < last['trend_ema_fast'] and last['trend_ema_fast'] < last['trend_ema_slow']:
        signals.append(f"EMA Fast = {last['trend_ema_fast']:.2f} < Slow Bearish = {last['trend_ema_slow']:.2f}")

    # Volatility Indicators
    if last['Close'] > last['volatility_bbh']:
        signals.append("Bollinger Band Upper Breakout")
    if last['Close'] < last['volatility_bbl']:
        signals.append("Bollinger Band Lower Breakdown")

    if last['Close'] > last['volatility_kch']:
        signals.append("Keltner Channel Upper Breakout")
    if last['Close'] < last['volatility_kcl']:
        signals.append("Keltner Channel Lower Breakdown")

    if last['Close'] > last['volatility_dch']:
        signals.append("Donchian Channel Upper Breakout")
    if last['Close'] < last['volatility_dcl']:
        signals.append("Donchian Channel Lower Breakdown")

    if last['volatility_atr'] > prev['volatility_atr'] * 1.5:
        signals.append("ATR Spike (Volatility Increase)")
    if last['volatility_ui'] > 20:
        signals.append(f"Ulcer Index High Risk ({last['volatility_ui']:.2f} > 20)")

    # Volume Indicators
    if last['volume_obv'] > prev['volume_obv'] and last['Close'] > prev['Close']:
        signals.append("OBV Increasing with Price")
    if last['volume_cmf'] > 0.1:
        signals.append(f"Positive Chaikin Money Flow ({last['volume_cmf']:.2f} > 0.1)")
    if last['volume_fi'] > 0 and prev['volume_fi'] < 0:
        signals.append("Force Index Bullish Crossover")
    if last['volume_vpt'] > prev['volume_vpt']:
        signals.append("Volume Price Trend Increasing")
    if last['volume_mfi'] > 80:
        signals.append(f"Money Flow Index Overbought ({last['volume_mfi']:.2f} > 80)")
    if last['volume_mfi'] < 20:
        signals.append(f"Money Flow Index Oversold ({last['volume_mfi']:.2f} < 20)")
    if last['volume_nvi'] > prev['volume_nvi']:
        signals.append("Negative Volume Index Bullish")

    # Others
    if last['others_dr'] > 2:
        signals.append(f"Daily Return Bullish ({(last['others_dr']*100):.2f}% > 2%)")
    if last['others_cr'] > 0:
        signals.append("Cumulative Return Positive")

    # ATR-based Risk Management
    if last['volatility_atr'] > 0:
        stop_loss = last['Close'] - 2 * last['volatility_atr']
        take_profit = last['Close'] + 3 * last['volatility_atr']
        signals.append(f"Risk Management: Stop-Loss={stop_loss:.2f}, Take-Profit={take_profit:.2f}")

    return signals

def backtest_signals(df, combo, look_forward=5, initial_capital=100000):
    """Backtest signal combinations with performance metrics"""
    cond = np.ones(len(df), dtype=bool)
    
    # Apply conditions for the combo
    for signal in combo:
        if signal == 'rsi_oversold':
            upper, lower = calculate_dynamic_thresholds(df, 'momentum_rsi')
            cond = cond & (df['momentum_rsi'] < lower)
        if signal == 'macd_bullish':
            cond = cond & (df['trend_macd'] > df['trend_macd_signal'])
        if signal == 'bb_breakout':
            cond = cond & (df['Close'] > df['volatility_bbh'])
        if signal == 'ichimoku_bullish':
            cond = cond & (df['Close'] > df['trend_ichimoku_a']) & (df['trend_ichimoku_a'] > df['trend_ichimoku_b'])
        if signal == 'adx_bullish':
            cond = cond & (df['trend_adx'] > 25) & (df['trend_adx_pos'] > df['trend_adx_neg'])
        if signal == 'stoch_oversold':
            cond = cond & (df['momentum_stoch_rsi_k'] < 20) & (df['momentum_stoch_rsi_d'] < 20)
        if signal == 'cci_oversold':
            cond = cond & (df['trend_cci'] < -100)
        if signal == 'cmf_positive':
            cond = cond & (df['volume_cmf'] > 0.1)
        if signal == 'vortex_bullish':
            cond = cond & (df['trend_vortex_ind_pos'] > df['trend_vortex_ind_neg'])
        if signal == 'trix_bullish':
            cond = cond & (df['trend_trix'] > 0)
        if signal == 'kst_bullish':
            cond = cond & (df['trend_kst'] > df['trend_kst_sig'])
        if signal == 'psar_bullish':
            cond = cond & (df['trend_psar_up_indicator'] == 1)
        if signal == 'mfi_oversold':
            cond = cond & (df['volume_mfi'] < 20)
        if signal == 'uo_oversold':
            cond = cond & (df['momentum_uo'] < 30)
        if signal == 'ao_bullish':
            cond = cond & (df['momentum_ao'] > 0)
        if signal == 'keltner_breakout':
            cond = cond & (df['Close'] > df['volatility_kch'])
        if signal == 'donchian_breakout':
            cond = cond & (df['Close'] > df['volatility_dch'])

    # Simulate trades
    trades = []
    position = 0
    entry_price = 0
    capital = initial_capital
    for i in np.where(cond)[0]:
        n=len(df)
        if i + look_forward < n and position == 0:
            entry_price = df.iloc[i]['Close']
            shares = capital // entry_price
            position = shares
            capital -= shares * entry_price
            exit_price = df.iloc[i + look_forward]['Close']
            capital += shares * exit_price
            returns = (exit_price - entry_price) / entry_price
            trades.append(returns)
            position = 0

    # Calculate performance metrics
    if trades:
        returns = np.array(trades)
        winrate = np.mean(returns > 0)
        avg_return = np.mean(returns)
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) != 0 else 0
        max_drawdown = np.min(np.cumsum(returns)) if len(returns) > 0 else 0
    else:
        winrate, avg_return, sharpe, max_drawdown = 0, 0, 0, 0

    return {
        'combo': combo,
        'winrate': winrate,
        'avg_return': avg_return,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'trade_count': len(trades)
    }

def optimize_signal_combo(df, combos=None):
    """Optimize signal combinations based on backtesting metrics"""
    if combos is None:
        combos = [
            ['rsi_oversold', 'macd_bullish', 'ichimoku_bullish'],
            ['adx_bullish', 'cmf_positive', 'vortex_bullish'],
            ['stoch_oversold', 'cci_oversold', 'trix_bullish'],
            ['mfi_oversold', 'uo_oversold', 'ao_bullish'],
            ['bb_breakout', 'keltner_breakout', 'donchian_breakout'],
            ['rsi_oversold', 'macd_bullish', 'kst_bullish', 'psar_bullish']
        ]
    
    results = []
    for combo in combos:
        result = backtest_signals(df, combo)
        results.append(result)
    
    # Sort by Sharpe ratio for risk-adjusted returns
    return sorted(results, key=lambda x: x['sharpe_ratio'], reverse=True)

def main():
    # Load and process data
    df = load_stock_data_yf("VCB", start="2024-01-01")

    df = add_technical_indicators_yf(df)
    
    # Detect latest signals
    signals = detect_signals(df)
    print("Latest Signals:")
    for signal in signals:
        print(signal)
        print()
    if signals:
        send_alert("VCB", signals, to_email="nghghung6904@gmail.com")
    
    # Optimize signal combinations
    optimized_results = optimize_signal_combo(df)
    print('------------------------------------------')
    print("Optimized Signal Combinations:")
    for result in optimized_results:
        print(result)

if __name__ == "__main__":
    main()