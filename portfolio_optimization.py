import pandas as pd
import numpy as np
# from vnstock import Vnstock
import yfinance as yf
from pypfopt import EfficientFrontier, risk_models, expected_returns, discrete_allocation
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def get_company_info_yf(ticker):
    """Lấy thông tin công ty từ Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            'name': info.get('longName', 'N/A'),
            'shortName': info.get('shortName', 'N/A'),
        }
    except Exception as e:
        # Error getting company info - log internally only
        pass
        return None

def load_stock_data_yf(ticker, asset_type='stock', start='2015-01-01', end=datetime.now().strftime('%Y-%m-%d'), interval='1d'):
    """Tải dữ liệu giá cổ phiếu từ Yahoo Finance"""
    if asset_type == 'stock':
        try:
            ticker = ticker.upper() + ".VN"
            df = yf.download(ticker, start=start, end=end, interval=interval)
            df.reset_index(inplace=True)

            return df
        except:
            df = yf.download(ticker, start=start, end=end, interval=interval)
            df.reset_index(inplace=True)

            return df
    elif asset_type == 'crypto':
        try:
            ticker = ticker.upper() + "-USD"
            df = yf.download(ticker, start=start, end=end, interval=interval)
            # Fix MultiIndex columns issue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns.values]
            df.reset_index(inplace=True)
            
            # Get USD/VND exchange rate for conversion
            try:
                usd_vnd_rate = yf.Ticker("USDVND=X").history(period="1d", interval="1m")["Close"].iloc[-1]
                # Only convert price columns to VND, keep Date and Volume unchanged
                price_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close']
                for col in price_columns:
                    if col in df.columns:
                        df[col] = df[col] * usd_vnd_rate
            except Exception as rate_error:
                # If can't get exchange rate, just return USD values
                print(f"Warning: Could not get USD/VND rate, returning USD values: {rate_error}")
                pass
            
            return df
        except Exception as e:
            print(f"Error loading crypto data for {ticker}: {e}")
            return None

# Hàm lấy dữ liệu từ vnstock3
def get_stock_data(symbols, asset_type, start_date, end_date, source='VCI'):
    df_all = pd.DataFrame()
    for symbol in symbols:
        try:
            # stock = Vnstock().stock(symbol=symbol, source=source)
            # df = stock.quote.history(start=start_date, end=end_date, interval='1D')
            df = load_stock_data_yf(symbol, asset_type=asset_type, start=start_date, end=end_date)
            # df = df[['time', 'close']].set_index('time')
            df = df[['Date', 'Close']].set_index('Date')
            df.columns = [symbol]
            if df_all.empty:
                df_all = df
            else:
                df_all = df_all.join(df, how='outer')
        except Exception as e:
            print(f"Không thể lấy dữ liệu cho {symbol}: {e}")
    return df_all.dropna()

def optimize_portfolio(symbols, asset_type, start_date, end_date, investment_amount, source='VCI'):
    """
    Tối ưu hóa danh mục đầu tư
    
    Args:
        symbols: Danh sách mã cổ phiếu
        start_date: Ngày bắt đầu
        end_date: Ngày kết thúc
        investment_amount: Số tiền đầu tư
        source: Nguồn dữ liệu
    
    Returns:
        dict: Kết quả tối ưu hóa danh mục
    """
    try:
        # Lấy dữ liệu
        prices_df = get_stock_data(symbols, asset_type, start_date, end_date, source)
        
        if prices_df.empty:
            raise ValueError("Không thể lấy dữ liệu cho các mã cổ phiếu")
        
        prices_df.index = pd.to_datetime(prices_df.index)
        
        # Tính toán lợi nhuận kỳ vọng và ma trận hiệp phương sai
        mu = expected_returns.mean_historical_return(prices_df)
        S = risk_models.sample_cov(prices_df)
        
        # Tối ưu hóa danh mục đầu tư với tỷ lệ Sharpe tối đa
        ef = EfficientFrontier(mu, S)
        weights = ef.max_sharpe()
        cleaned_weights = ef.clean_weights()
        
        # Tính toán hiệu suất danh mục
        portfolio_performance = ef.portfolio_performance(verbose=False)
        expected_return, annual_volatility, sharpe_ratio = portfolio_performance
        
        # Phân bổ số lượng cổ phiếu (floating point để chính xác với phần trăm)
        latest_prices = discrete_allocation.get_latest_prices(prices_df)
        allocation = {}
        for symbol, weight in cleaned_weights.items():
            if weight > 0:
                investment_for_symbol = investment_amount * weight
                shares = investment_for_symbol / latest_prices[symbol]
                allocation[symbol] = shares
        
        leftover = 0  # Không còn tiền thừa khi sử dụng floating point
        
        # Chuẩn bị kết quả
        result = {
            'success': True,
            'expected_return': float(expected_return),
            'annual_volatility': float(annual_volatility),
            'sharpe_ratio': float(sharpe_ratio),
            'weights': {symbol: float(weight) for symbol, weight in cleaned_weights.items()},
            'allocation': {symbol: float(shares) for symbol, shares in allocation.items()},
            'latest_prices': {symbol: float(price) for symbol, price in latest_prices.items()},
            'leftover': float(leftover),
            'total_investment': float(investment_amount)
        }
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def calculate_manual_portfolio(manual_weights, asset_type, start_date, end_date, investment_amount, source='VCI'):
    """
    Tính toán hiệu suất danh mục thủ công
    
    Args:
        manual_weights: Dict với tỷ trọng thủ công {symbol: weight}
        start_date: Ngày bắt đầu
        end_date: Ngày kết thúc
        investment_amount: Số tiền đầu tư
        source: Nguồn dữ liệu
    
    Returns:
        dict: Kết quả tính toán danh mục thủ công
    """
    try:
        symbols = list(manual_weights.keys())
        
        # Lấy dữ liệu
        prices_df = get_stock_data(symbols, asset_type, start_date, end_date, source)
        if prices_df.empty:
            raise ValueError("Không thể lấy dữ liệu cho các mã cổ phiếu")
        
        prices_df.index = pd.to_datetime(prices_df.index)
        
        # Tính toán lợi nhuận kỳ vọng và ma trận hiệp phương sai
        mu = expected_returns.mean_historical_return(prices_df)
        S = risk_models.sample_cov(prices_df)
        
        # Tính toán hiệu suất với tỷ trọng thủ công
        weights_array = np.array([manual_weights[symbol] for symbol in symbols])
        
        # Tính toán lợi nhuận kỳ vọng
        portfolio_return = np.dot(weights_array, mu)
        
        # Tính toán độ biến động
        portfolio_volatility = np.sqrt(np.dot(weights_array.T, np.dot(S, weights_array)))
        
        # Tính toán tỷ lệ Sharpe (giả sử risk-free rate = 0)
        sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility != 0 else 0
        
        # Phân bổ số lượng cổ phiếu (floating point để chính xác với phần trăm)
        latest_prices = discrete_allocation.get_latest_prices(prices_df)
        allocation = {}
        for symbol, weight in manual_weights.items():
            if weight > 0:
                investment_for_symbol = investment_amount * weight
                shares = investment_for_symbol / latest_prices[symbol]
                allocation[symbol] = shares
        
        leftover = 0  # Không còn tiền thừa khi sử dụng floating point
        
        # Chuẩn bị kết quả
        result = {
            'success': True,
            'expected_return': float(portfolio_return),
            'annual_volatility': float(portfolio_volatility),
            'sharpe_ratio': float(sharpe_ratio),
            'weights': {symbol: float(weight) for symbol, weight in manual_weights.items()},
            'allocation': {symbol: float(shares) for symbol, shares in allocation.items()},
            'latest_prices': {symbol: float(price) for symbol, price in latest_prices.items()},
            'leftover': float(leftover),
            'total_investment': float(investment_amount)
        }
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

# Demo script (chỉ chạy khi file được execute trực tiếp)
if __name__ == "__main__":
    # Tham số đầu vào
    symbols = ['VCB', 'BID', 'CTG', 'MBB', 'TCB']  # Danh sách mã cổ phiếu
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    investment_amount = 1000000000  # 1 tỷ VND

    # Tối ưu hóa danh mục
    result = optimize_portfolio(symbols, 'stock', start_date, end_date, investment_amount)
    
    if result['success']:
        print("\n=== Thông số kỹ thuật của danh mục tối ưu ===")
        print(f"\n1. Hiệu suất danh mục:")
        print(f" - Lợi nhuận kỳ vọng hàng năm: {result['expected_return']:.4f}")
        print(f" - Độ biến động hàng năm: {result['annual_volatility']:.4f}")
        print(f" - Tỷ lệ Sharpe: {result['sharpe_ratio']:.4f}")
        
        print(f"\n2. Tỷ trọng danh mục tối ưu:")
        for symbol, weight in result['weights'].items():
            print(f"{symbol}: {weight:.4f}")
        
        print(f"\n3. Số lượng cổ phiếu đề xuất:")
        for symbol, shares in result['allocation'].items():
            print(f"{symbol}: {shares:.4f} cổ phiếu")
        
        print(f"\n4. Số tiền còn lại: {result['leftover']:,.0f} VND")
    else:
        # Error in portfolio optimization - log internally only
        pass
