# Gọi các thư viện python để sử dụng
from datetime import date
import pandas as pd
import numpy as np
from prophet import Prophet
import matplotlib.pyplot as plt
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

# Import vnquant data loader
from data_loader import load_stock_data_vn

# selected_stock = 'SSI' # SOME RANDOM STOCK

# Tạo hàm load_data sử dụng vnquant để tải dữ liệu
def load_data(ticker, start_date='2011-01-01', end_date=None):
    """
    Tải dữ liệu cổ phiếu từ vnquant
    Args:
        ticker: Mã cổ phiếu (VD: 'VCB', 'SSI')
        start_date: Ngày bắt đầu
        end_date: Ngày kết thúc (mặc định là hôm nay)
    Returns:
        DataFrame: Dữ liệu cổ phiếu
    """
    if end_date is None:
        end_date = date.today().strftime("%Y-%m-%d")
    
    # Sử dụng vnquant để tải dữ liệu
    data = load_stock_data_vn(ticker, start=start_date, end=end_date)
    
    # Xử lý MultiIndex columns từ vnquant
    if isinstance(data.columns, pd.MultiIndex):
        # Flatten MultiIndex columns
        data.columns = [col[0] if col[0] != '' else col[1] for col in data.columns]
    
    # Đổi tên cột date thành time để consistent
    if 'date' in data.columns:
        data = data.rename(columns={'date': 'time'})
    
    # Đảm bảo cột time là datetime
    if 'time' in data.columns:
        data['time'] = pd.to_datetime(data['time'])
    
    return data

# # Gọi dữ liệu từ hàm load_data
# data = load_data(selected_stock, start_date='2020-01-01')

# # Chuẩn bị dữ liệu cho Prophet
# n_months = 1 # SOME RANDOM NUMBER OF MONTHS FOR PREDICTION
# period = n_months * 30

# # Chuẩn bị dữ liệu training cho Prophet
# df_train = data[['time', 'close']].copy()
# df_train = df_train.rename(columns={"time": "ds", "close": "y"})

# # Đảm bảo cột 'ds' là datetime
# df_train['ds'] = pd.to_datetime(df_train['ds'])

# # Loại bỏ các giá trị null
# df_train = df_train.dropna()

# # Sắp xếp theo thời gian
# df_train = df_train.sort_values('ds').reset_index(drop=True)

# # Train model Prophet
# print("Đang training mô hình Prophet...")
# m = Prophet(
#     daily_seasonality=False,
#     weekly_seasonality=True,
#     yearly_seasonality=True,
#     changepoint_prior_scale=0.05,
#     seasonality_prior_scale=10.0,
#     interval_width=0.95
# )

# m.fit(df_train)

# # Tạo dataframe cho dự báo
# future = m.make_future_dataframe(periods=period)
# forecast = m.predict(future)

# # Xử lý kết quả forecast
# forecast_result = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper', 'trend', 'trend_lower', 'trend_upper']].copy()
# forecast_result['ds'] = pd.to_datetime(forecast_result['ds']).dt.date
# forecast_result = forecast_result.rename(columns={
#     "ds": "time", 
#     "yhat": "predicted_price", 
#     'yhat_lower': 'pred_price_lower', 
#     'yhat_upper': 'pred_price_upper'
# })

# print(f"Dự báo hoàn thành cho mã {selected_stock}")
# print(f"Dự báo {period} ngày tới")
# print(f"Giá hiện tại: {df_train['y'].iloc[-1]:,.0f} VND")
# print(f"Giá dự báo cuối: {forecast['yhat'].iloc[-1]:,.0f} VND")
# print(f"Khoảng tin cậy: {forecast['yhat_lower'].iloc[-1]:,.0f} - {forecast['yhat_upper'].iloc[-1]:,.0f} VND")

# Tạo class StockAnalysis để phân tích nâng cao
class StockAnalysis:
    def __init__(self, symbol):
        self.symbol = symbol
        self.data = None
        self.model = None
        self.forecast = None
        
    def load_data(self, start_date='2011-01-01', end_date=None):
        """Load dữ liệu cổ phiếu"""
        self.data = load_data(self.symbol, start_date, end_date)
        return self.data
    
    def prepare_prophet_data(self):
        """Chuẩn bị dữ liệu cho Prophet"""
        # Xử lý MultiIndex columns nếu có
        if isinstance(self.data.columns, pd.MultiIndex):
            # Flatten MultiIndex columns
            self.data.columns = [col[0] if col[0] != '' else col[1] for col in self.data.columns]
        
        # Đổi tên cột date thành time nếu cần
        if 'date' in self.data.columns:
            self.data = self.data.rename(columns={'date': 'time'})
        
        # Debug: Print column names and sample data
        # print(f"Data columns: {self.data.columns.tolist()}")
        # print(f"Data shape: {self.data.shape}")
        # if not self.data.empty:
        #     print(f"First few rows:\n{self.data.head()}")
        #     print(f"Last few rows:\n{self.data.tail()}")
        
        # Chuẩn bị dữ liệu cho Prophet
        df = self.data[['time', 'close']].copy()
        df = df.rename(columns={"time": "ds", "close": "y"})
        df['ds'] = pd.to_datetime(df['ds'])
        df = df.dropna().sort_values('ds').reset_index(drop=True)
        
        # Đảm bảo cột y là numeric
        df['y'] = pd.to_numeric(df['y'], errors='coerce')
        df = df.dropna()
        
        # Debug: Check processed data
        # print(f"Processed data shape: {df.shape}")
        # if not df.empty:
        #     print(f"Price range: {df['y'].min()} - {df['y'].max()}")
        #     print(f"Last price: {df['y'].iloc[-1]}")
        
        return df
    
    def train_prophet(self, df_train):
        """Train mô hình Prophet"""
        self.model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0,
            interval_width=0.95
        )
        self.model.fit(df_train)
        return self.model
    
    def predict(self, periods=30):
        """Dự báo giá cổ phiếu"""
        if self.model is None:
            raise ValueError("Model chưa được train!")
        
        future = self.model.make_future_dataframe(periods=periods)
        self.forecast = self.model.predict(future)
        return self.forecast
    
    def evaluate_model(self, df_train):
        """Đánh giá độ chính xác mô hình"""
        if self.forecast is None:
            raise ValueError("Chưa có dự báo!")
        
        # Lấy dữ liệu training để so sánh
        train_forecast = self.forecast[self.forecast['ds'].isin(df_train['ds'])]
        actual = df_train['y'].values
        predicted = train_forecast['yhat'].values
        
        # Tính các metric
        mae = mean_absolute_error(actual, predicted)
        rmse = np.sqrt(mean_squared_error(actual, predicted))
        
        # Handle division by zero for MAPE
        try:
            # Avoid division by zero
            actual_nonzero = actual[actual != 0]
            predicted_nonzero = predicted[actual != 0]
            if len(actual_nonzero) > 0:
                mape = np.mean(np.abs((actual_nonzero - predicted_nonzero) / actual_nonzero)) * 100
            else:
                mape = 0.0
        except:
            mape = 0.0
        
        return {
            'mae': mae,
            'rmse': rmse,
            'mape': mape
        }
    
    def analyze(self, start_date='2011-01-01', forecast_periods=30):
        """Phân tích toàn diện cổ phiếu"""
        try:
            # Load và chuẩn bị dữ liệu
            self.load_data(start_date)
            df_train = self.prepare_prophet_data()
            
            # Train model
            self.train_prophet(df_train)
            
            # Dự báo
            forecast = self.predict(forecast_periods)
            
            # Đánh giá model
            evaluation = self.evaluate_model(df_train)
            
            # Tạo summary - ensure we have valid data
            if len(df_train) == 0:
                raise ValueError("Không có dữ liệu để phân tích")
            
            current_price = df_train['y'].iloc[-1]
            predicted_price = forecast['yhat'].iloc[-1]
            
            # Ensure current_price is not zero or NaN
            if pd.isna(current_price) or current_price == 0:
                # Try to get the last valid price
                valid_prices = df_train['y'].dropna()
                valid_prices = valid_prices[valid_prices > 0]
                if len(valid_prices) > 0:
                    current_price = valid_prices.iloc[-1]
                else:
                    current_price = 1.0  # Default to prevent division by zero
            
            price_change = predicted_price - current_price
            
            # Handle division by zero for price_change_pct
            if current_price != 0 and not pd.isna(current_price):
                price_change_pct = (price_change / current_price) * 100
            else:
                price_change_pct = 0.0
            
            # Convert forecast data to JSON-serializable format
            forecast_data = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(forecast_periods).copy()
            
            # Convert datetime to string and handle NaN values
            forecast_data['ds'] = forecast_data['ds'].dt.strftime('%Y-%m-%d')
            forecast_data = forecast_data.fillna(0)  # Replace NaN with 0
            
            # Helper function to safely convert to float and handle inf/nan
            def safe_float(value):
                if pd.isna(value) or np.isinf(value) or value == float('inf') or value == float('-inf'):
                    return 0.0
                try:
                    result = float(value)
                    if np.isinf(result) or np.isnan(result):
                        return 0.0
                    return result
                except (ValueError, TypeError):
                    return 0.0
            
            summary = {
                'symbol': self.symbol,
                'current_price': safe_float(current_price),
                'predicted_price_30d': safe_float(predicted_price),
                'price_change': safe_float(price_change),
                'price_change_pct': safe_float(price_change_pct),
                'trend': 'Tăng' if price_change > 0 else 'Giảm',
                'max_predicted_price': safe_float(forecast['yhat_upper'].iloc[-1]),
                'min_predicted_price': safe_float(forecast['yhat_lower'].iloc[-1]),
                'avg_uncertainty': safe_float((forecast['yhat_upper'].iloc[-1] - forecast['yhat_lower'].iloc[-1]) / 2),
                'forecast_data': forecast_data.to_dict('records')
            }
            
            # Convert evaluation metrics to native Python types
            evaluation_clean = {
                'mae': safe_float(evaluation['mae']),
                'rmse': safe_float(evaluation['rmse']),
                'mape': safe_float(evaluation['mape'])
            }
            
            return {
                'success': True,
                'summary': summary,
                'evaluation': evaluation_clean
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

def analyze_stock(symbol, start_date='2020-01-01', forecast_periods=30):
    """Hàm tiện ích để phân tích cổ phiếu"""
    analyzer = StockAnalysis(symbol)
    return analyzer.analyze(start_date, forecast_periods)

# # Test stock analysis với VCB
# print("\n=== PHÂN TÍCH CỔ PHIẾU VCB ===")
# result = analyze_stock('VCB', start_date='2022-01-01', forecast_periods=30)

# if result['success']:
#     summary = result['summary']
#     print(f"Mã cổ phiếu: {summary['symbol']}")
#     print(f"Giá hiện tại: {summary['current_price']:,} VND")
#     print(f"Dự báo 30 ngày: {summary['predicted_price_30d']:,} VND")
#     print(f"Thay đổi: {summary['price_change']:,} VND ({summary['price_change_pct']:.2f}%)")
#     print(f"Xu hướng: {summary['trend']}")
#     print(f"Giá cao nhất dự báo: {summary['max_predicted_price']:,} VND")
#     print(f"Giá thấp nhất dự báo: {summary['min_predicted_price']:,} VND")
    
#     if result['evaluation']:
#         print(f"\n=== ĐÁNH GIÁ MÔ HÌNH ===")
#         eval_data = result['evaluation']
#         print(f"MAE: {eval_data['mae']:,}")
#         print(f"RMSE: {eval_data['rmse']:,}")
#         print(f"MAPE: {eval_data['mape']:.2f}%")
# else:
#     print(f"Lỗi: {result['error']}")

# # So sánh kết quả Prophet cơ bản vs Stock Analysis module
# print("\n=== SO SÁNH PROPHET CƠ BẢN VS STOCK ANALYSIS MODULE ===")

# # Prophet cơ bản (code được cải tiến)
# print("\n1. PROPHET CƠ BẢN (Cải tiến với vnquant):")
# print(f"Dự báo cuối: {forecast['yhat'].iloc[-1]:,.0f} VND")
# print(f"Khoảng tin cậy: {forecast['yhat_lower'].iloc[-1]:,.0f} - {forecast['yhat_upper'].iloc[-1]:,.0f} VND")

# # Stock Analysis module (nâng cao)
# print("\n2. STOCK ANALYSIS MODULE (Nâng cao):")
# if result['success']:
#     summary = result['summary']
#     print(f"Dự báo cuối: {summary['predicted_price_30d']:,.0f} VND")
#     print(f"Khoảng tin cậy: {summary['min_predicted_price']:,.0f} - {summary['max_predicted_price']:,.0f} VND")
#     print(f"Độ tin cậy trung bình: ±{summary['avg_uncertainty']:,.0f} VND")
    
#     # Hiển thị 5 ngày dự báo đầu tiên
#     print(f"\n=== 5 NGÀY DỰ BÁO ĐẦU TIÊN ===")
#     for i, row in enumerate(summary['forecast_data'][:5]):
#         date = pd.to_datetime(row['ds']).strftime('%d/%m/%Y')
#         price = row['yhat']
#         lower = row['yhat_lower']
#         upper = row['yhat_upper']
#         print(f"{date}: {price:,.0f} VND ({lower:,.0f} - {upper:,.0f})")

# print("\n=== TÍNH NĂNG BỔ SUNG CỦA STOCK ANALYSIS MODULE ===")
# print("✓ Sử dụng vnquant để tải dữ liệu cổ phiếu Việt Nam")
# print("✓ Đánh giá độ chính xác mô hình (MAE, RMSE, MAPE)")
# print("✓ Biểu đồ dự báo với khoảng tin cậy")
# print("✓ Phân tích thành phần (trend, seasonal)")
# print("✓ Tóm tắt thống kê chi tiết")
# print("✓ Xử lý lỗi và validation dữ liệu")
# print("✓ Hỗ trợ xuất biểu đồ base64 cho web")
# print("✓ Tích hợp hoàn toàn với hệ sinh thái vnquant")

# # Vẽ biểu đồ dự báo
# print("\n=== VẼ BIỂU ĐỒ DỰ BÁO ===")
# try:
#     fig1 = m.plot(forecast, include_legend=True)
#     plt.title(f'Dự báo giá cổ phiếu {selected_stock}')
#     plt.ylabel('Giá (VND)')
#     plt.xlabel('Thời gian')
#     plt.show()
    
#     # Biểu đồ thành phần
#     fig2 = m.plot_components(forecast)
#     plt.suptitle(f'Phân tích thành phần dự báo {selected_stock}')
#     plt.show()
    
# except Exception as e:
#     print(f"Không thể vẽ biểu đồ: {e}")

# print("\n=== HOÀN THÀNH PHÂN TÍCH ===")
# print("File stock_analysis.py đã được cập nhật để sử dụng:")
# print("- Prophet cho dự báo cổ phiếu")
# print("- vnquant (load_stock_data_vn) để tải dữ liệu")
# print("- Các tính năng phân tích nâng cao")
# print("- Đánh giá mô hình và báo cáo chi tiết")