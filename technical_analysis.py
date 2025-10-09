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

    # ==================== MOMENTUM INDICATORS ====================
    # RSI (Relative Strength Index - Chỉ số sức mạnh tương đối)
    rsi_upper, rsi_lower = calculate_dynamic_thresholds(df, 'momentum_rsi')
    
    if last['momentum_rsi'] < rsi_lower.iloc[-1]:
        signals.append({
            'signal': f"RSI Oversold ({last['momentum_rsi']:.2f} < {rsi_lower.iloc[-1]:.2f})",
            'explanation': "RSI OVERSOLD - Thị trường đang BÁN QUÁ MỨC. RSI (0-100) đo lường tốc độ và độ biến động của giá. Khi RSI thấp hơn ngưỡng dưới, có nghĩa là áp lực bán quá lớn và giá có thể sắp tăng trở lại (tín hiệu MUA tiềm năng). Giống như một sợi dây cao su bị kéo căng quá mức sẽ phản đẩy lại."
        })
    
    if last['momentum_rsi'] > rsi_upper.iloc[-1]:
        signals.append({
            'signal': f"RSI Overbought ({last['momentum_rsi']:.2f} > {rsi_upper.iloc[-1]:.2f})",
            'explanation': "RSI OVERBOUGHT - Thị trường đang MUA QUÁ MỨC. Khi RSI vượt ngưỡng trên, áp lực mua đã quá lớn và giá có thể sắp giảm xuống (tín hiệu BÁN tiềm năng). Thị trường cần 'nghỉ ngơi' sau khi tăng quá nhanh."
        })

    # Stochastic RSI
    if last['momentum_stoch_rsi_k'] < 20 and last['momentum_stoch_rsi_d'] < 20:
        signals.append({
            'signal': f"Stochastic RSI Oversold (K = {last['momentum_stoch_rsi_k']:.2f} < 20, D = {last['momentum_stoch_rsi_d']:.2f} < 20)",
            'explanation': "STOCHASTIC RSI OVERSOLD - BÁN QUÁ MỨC NÂNG CAO. Đây là phiên bản nhạy cảm hơn của RSI, so sánh giá đóng cửa hiện tại với biên độ dao động gần đây. Khi cả K và D đều dưới 20, đây là tín hiệu MUA mạnh vì giá đang ở mức thấp bất thường so với chu kỳ gần đây. Hữu ích cho việc tìm điểm vào lệnh ngắn hạn."
        })
    
    if last['momentum_stoch_rsi_k'] > 80 and last['momentum_stoch_rsi_d'] > 80:
        signals.append({
            'signal': f"Stochastic RSI Overbought (K = {last['momentum_stoch_rsi_k']:.2f} > 80, D = {last['momentum_stoch_rsi_d']:.2f} > 80)",
            'explanation': "STOCHASTIC RSI OVERBOUGHT - MUA QUÁ MỨC NÂNG CAO. Khi cả K và D vượt 80, giá đang ở mức cao bất thường và có thể sắp điều chỉnh giảm (tín hiệu BÁN). Đây là cảnh báo sớm về việc thị trường có thể đảo chiều xuống."
        })

    # CCI (Commodity Channel Index)
    if last['trend_cci'] < -100:
        signals.append({
            'signal': f"CCI Oversold ({last['trend_cci']:.2f} < -100)",
            'explanation': "CCI OVERSOLD - GIÁ THẤP BẤT THƯỜNG. CCI đo lường sự chênh lệch giữa giá hiện tại và giá trung bình trong một khoảng thời gian. Khi CCI < -100, giá đang thấp hơn nhiều so với mức trung bình lịch sử, báo hiệu cơ hội MUA tốt. Thường thấy ở đáy của xu hướng giảm."
        })
    
    if last['trend_cci'] > 100:
        signals.append({
            'signal': f"CCI Overbought ({last['trend_cci']:.2f} > 100)",
            'explanation': "CCI OVERBOUGHT - GIÁ CAO BẤT THƯỜNG. Khi CCI > 100, giá đã vượt xa mức trung bình và có thể sắp điều chỉnh giảm (tín hiệu BÁN). Cảnh báo rằng đà tăng có thể đã quá mạnh và cần hạ nhiệt."
        })

    # TSI (True Strength Index)
    if last['momentum_tsi'] < -25:
        signals.append({
            'signal': f"TSI Oversold ({last['momentum_tsi']:.2f} < -25)",
            'explanation': "TSI OVERSOLD - ĐÀ GIẢM YẾU DẦN. TSI sử dụng kỹ thuật làm mượt kép để lọc nhiễu và xác định xu hướng thực sự. Khi TSI < -25, đà giảm giá đã quá mạnh và sắp cạn kiệt, tạo cơ hội MUA. Đây là chỉ báo ít bị 'tín hiệu giả' hơn các chỉ báo động lượng khác."
        })
    
    if last['momentum_tsi'] > 25:
        signals.append({
            'signal': f"TSI Overbought ({last['momentum_tsi']:.2f} > 25)",
            'explanation': "TSI OVERBOUGHT - ĐÀ TĂNG YẾU DẦN. Khi TSI > 25, đà tăng giá đã rất mạnh và có thể sắp suy yếu (tín hiệu BÁN). Thị trường cần thời gian để 'hạ nhiệt' trước khi tiếp tục tăng."
        })

    # Ultimate Oscillator
    if last['momentum_uo'] < 30:
        signals.append({
            'signal': f"Ultimate Oscillator Oversold ({last['momentum_uo']:.2f} < 30)",
            'explanation': "ULTIMATE OSCILLATOR OVERSOLD - ÁP LỰC BÁN CẠNH KIỆT. Chỉ báo này kết hợp 3 khung thời gian khác nhau (ngắn, trung, dài hạn) để giảm tín hiệu giả. Khi < 30, áp lực bán từ nhiều nhóm nhà đầu tư đã quá lớn và giá sắp phục hồi (tín hiệu MUA đáng tin cậy)."
        })
    
    if last['momentum_uo'] > 70:
        signals.append({
            'signal': f"Ultimate Oscillator Overbought ({last['momentum_uo']:.2f} > 70)",
            'explanation': "ULTIMATE OSCILLATOR OVERBOUGHT - ÁP LỰC MUA CẠNH KIỆT. Khi > 70, áp lực mua từ nhiều khung thời gian đã quá lớn và giá có thể sắp giảm (tín hiệu BÁN). Đây là dấu hiệu cảnh báo mạnh vì phân tích từ nhiều góc độ thời gian."
        })

    # Stochastic Oscillator
    if last['momentum_stoch'] < 20:
        signals.append({
            'signal': f"Stochastic Oversold ({last['momentum_stoch']:.2f} < 20)",
            'explanation': "STOCHASTIC OVERSOLD - GIÁ ĐÓNG CỬA GẦN ĐÁY. Stochastic so sánh giá đóng cửa với biên độ cao-thấp trong một khoảng thời gian. Khi < 20, giá đóng cửa gần với mức thấp nhất gần đây, cho thấy người bán đang chiếm ưu thế nhưng sắp cạn kiệt (tín hiệu MUA). Đặc biệt hữu ích trong thị trường sideway."
        })
    
    if last['momentum_stoch'] > 80:
        signals.append({
            'signal': f"Stochastic Overbought ({last['momentum_stoch']:.2f} > 80)",
            'explanation': "STOCHASTIC OVERBOUGHT - GIÁ ĐÓNG CỬA GẦN ĐỈNH. Khi > 80, giá đóng cửa gần với mức cao nhất gần đây, người mua đang mạnh nhưng sắp mệt (tín hiệu BÁN). Cần cẩn trọng vì trong xu hướng tăng mạnh, chỉ số này có thể ở trạng thái overbought kéo dài."
        })

    # Williams %R
    if last['momentum_wr'] < -80:
        signals.append({
            'signal': f"Williams %R Oversold ({last['momentum_wr']:.2f} < -80)",
            'explanation': "WILLIAMS %R OVERSOLD - GIÁ GẦN ĐÁY NGẮN HẠN. Williams %R đo lường mức độ giá đóng cửa so với biên độ cao nhất trong chu kỳ. Khi < -80 (gần -100), giá đang ở vùng thấp nhất và có thể bật lên (tín hiệu MUA). Chỉ báo này rất nhạy, phù hợp với giao dịch ngắn hạn và swing trading."
        })
    
    if last['momentum_wr'] > -20:
        signals.append({
            'signal': f"Williams %R Overbought ({last['momentum_wr']:.2f} > -20)",
            'explanation': "WILLIAMS %R OVERBOUGHT - GIÁ GẦN ĐỈNH NGẮN HẠN. Khi > -20 (gần 0), giá đang ở vùng cao nhất chu kỳ và có thể điều chỉnh xuống (tín hiệu BÁN). Hữu ích để xác định điểm thoát lệnh trong giao dịch ngắn hạn."
        })

    # Awesome Oscillator
    if last['momentum_ao'] > 0 and prev['momentum_ao'] < 0:
        signals.append({
            'signal': f"Awesome Oscillator Bullish Crossover (Last AO = {last['momentum_ao']:.2f} > 0, Previous AO = {prev['momentum_ao']:.2f} < 0)",
            'explanation': "AWESOME OSCILLATOR TĂNG GIÁ - ĐỘNG LỰC CHUYỂN HƯỚNG TÍCH CỰC. AO đo lường sự khác biệt giữa động lượng ngắn hạn và dài hạn. Khi AO vượt qua 0 từ dưới lên, động lực ngắn hạn đang mạnh hơn động lực dài hạn, báo hiệu xu hướng tăng đang hình thành (tín hiệu MUA). Đây là dấu hiệu của sự thay đổi tâm lý thị trường từ tiêu cực sang tích cực."
        })
    
    if last['momentum_ao'] < 0 and prev['momentum_ao'] > 0:
        signals.append({
            'signal': f"Awesome Oscillator Bearish Crossover (Last AO = {last['momentum_ao']:.2f} < 0, Previous AO = {prev['momentum_ao']:.2f} > 0)",
            'explanation': "AWESOME OSCILLATOR GIẢM GIÁ - ĐỘNG LỰC CHUYỂN HƯỚNG TIÊU CỰC. Khi AO cắt xuống dưới 0, động lực ngắn hạn đang yếu hơn động lực dài hạn, xu hướng giảm đang hình thành (tín hiệu BÁN). Thị trường đang chuyển từ tâm lý tích cực sang tiêu cực."
        })

    # ROC (Rate of Change)
    if last['momentum_roc'] > 5:
        signals.append({
            'signal': f"ROC Bullish ({last['momentum_roc']:.2f} > 5)",
            'explanation': "ROC TĂNG GIÁ - TỐC ĐỘ TĂNG NHANH. ROC đo lường phần trăm thay đổi giá trong một khoảng thời gian. Khi ROC > 5%, giá đang tăng nhanh (tăng hơn 5% so với trước đó), cho thấy động lượng mua mạnh mẽ (tín hiệu MUA). Tuy nhiên cần cẩn trọng nếu ROC quá cao (>15-20%) vì có thể là dấu hiệu mua quá mức."
        })
    
    if last['momentum_roc'] < -5:
        signals.append({
            'signal': f"ROC Bearish ({last['momentum_roc']:.2f} < -5)",
            'explanation': "ROC GIẢM GIÁ - TỐC ĐỘ GIẢM NHANH. Khi ROC < -5%, giá đang giảm nhanh (giảm hơn 5%), cho thấy áp lực bán mạnh (tín hiệu BÁN hoặc chờ đợi). Nếu ROC quá âm (<-15%), có thể là cơ hội mua đáy cho nhà đầu tư dài hạn."
        })

    # PPO (Percentage Price Oscillator)
    if last['momentum_ppo'] > last['momentum_ppo_signal']:
        signals.append({
            'signal': "PPO Bullish Crossover",
            'explanation': "PPO CẮT TĂNG - ĐỘNG LỰC GIÁ CHUYỂN TÍCH CỰC. PPO tương tự MACD nhưng tính bằng phần trăm, dễ so sánh giữa các mã. Khi đường PPO cắt lên trên đường tín hiệu, đà tăng giá đang mạnh lên (tín hiệu MUA). Đây là dấu hiệu sớm của xu hướng tăng, đặc biệt mạnh nếu xảy ra từ vùng âm."
        })
    
    if last['momentum_ppo'] < last['momentum_ppo_signal']:
        signals.append({
            'signal': "PPO Bearish Crossover",
            'explanation': "PPO CẮT GIẢM - ĐỘNG LỰC GIÁ CHUYỂN TIÊU CỰC. Khi đường PPO cắt xuống dưới đường tín hiệu, đà giảm giá đang mạnh lên (tín hiệu BÁN). Đây là cảnh báo sớm về xu hướng giảm sắp tới."
        })

    # ==================== TREND INDICATORS ====================
    # MACD (Moving Average Convergence Divergence)
    if prev['trend_macd'] < prev['trend_macd_signal'] and last['trend_macd'] > last['trend_macd_signal']:
        signals.append({
            'signal': "MACD Bullish Crossover",
            'explanation': "MACD CẮT TĂNG - XU HƯỚNG TĂNG ĐANG HÌNH THÀNH. MACD là một trong những chỉ báo phổ biến nhất, đo lường mối quan hệ giữa hai đường trung bình động. Khi đường MACD cắt lên trên đường Signal, đây là tín hiệu MUA mạnh, cho thấy xu hướng tăng giá đang bắt đầu. Đặc biệt đáng tin cậy khi xảy ra từ vùng dưới 0 hoặc khi histogram MACD chuyển từ âm sang dương."
        })
    
    if prev['trend_macd'] > prev['trend_macd_signal'] and last['trend_macd'] < last['trend_macd_signal']:
        signals.append({
            'signal': "MACD Bearish Crossover",
            'explanation': "MACD CẮT GIẢM - XU HƯỚNG GIẢM ĐANG HÌNH THÀNH. Khi đường MACD cắt xuống dưới đường Signal, đây là tín hiệu BÁN, xu hướng giảm đang bắt đầu. Nên thoát lệnh hoặc đặt stop-loss chặt hơn. Tín hiệu mạnh hơn nếu xảy ra từ vùng trên 0."
        })

    # Ichimoku Cloud
    if last['Close'] > last['trend_ichimoku_a'] and last['trend_ichimoku_a'] > last['trend_ichimoku_b']:
        signals.append({
            'signal': "Ichimoku Bullish (Price above Cloud)",
            'explanation': "ICHIMOKU TĂNG GIÁ - GIÁ TRÊN MÂY. Ichimoku là hệ thống chỉ báo toàn diện của Nhật Bản. 'Đám mây' (Cloud/Kumo) được tạo bởi hai đường Senkou Span A và B, đại diện cho vùng hỗ trợ/kháng cự động. Khi giá ở trên đám mây VÀ Senkou A trên Senkou B, đây là xu hướng tăng rất mạnh (tín hiệu MUA/GIỮ). Đám mây hoạt động như 'tấm đệm' hỗ trợ giá."
        })
    
    if last['Close'] < last['trend_ichimoku_a'] and last['trend_ichimoku_a'] < last['trend_ichimoku_b']:
        signals.append({
            'signal': "Ichimoku Bearish (Price below Cloud)",
            'explanation': "ICHIMOKU GIẢM GIÁ - GIÁ DƯỚI MÂY. Khi giá ở dưới đám mây VÀ Senkou A dưới Senkou B, đây là xu hướng giảm mạnh (tín hiệu BÁN/TRÁNH MUA). Đám mây hoạt động như 'trần kháng cự' ngăn giá tăng lên."
        })

    # ADX (Average Directional Index)
    if last['trend_adx'] > 25 and last['trend_adx_pos'] > last['trend_adx_neg']:
        signals.append({
            'signal': f"Strong Bullish Trend (ADX = {last['trend_adx']:.2f} > 25, +DI = {last['trend_adx_pos']:.2f} > -DI = {last['trend_adx_neg']:.2f})",
            'explanation': "ADX - XU HƯỚNG TĂNG MẠNH. ADX đo lường SỨC MẠNH của xu hướng (không phải hướng). ADX > 25 nghĩa là có xu hướng rõ ràng. Khi +DI (Directional Indicator dương) > -DI, hướng là tăng. Đây là tín hiệu MUA/GIỮ mạnh vì xu hướng tăng đang rất khỏe. ADX > 40 là xu hướng cực mạnh, > 60 là siêu xu hướng (nhưng cẩn thận vì có thể sắp đảo chiều)."
        })
    
    if last['trend_adx'] > 25 and last['trend_adx_neg'] > last['trend_adx_pos']:
        signals.append({
            'signal': f"Strong Bearish Trend (ADX = {last['trend_adx']:.2f} > 25, +DI = {last['trend_adx_pos']:.2f} < -DI = {last['trend_adx_neg']:.2f})",
            'explanation': "ADX - XU HƯỚNG GIẢM MẠNH. ADX > 25 và -DI > +DI cho thấy xu hướng giảm rõ ràng và mạnh mẽ (tín hiệu BÁN/TRÁNH). Không nên giao dịch ngược xu hướng này. Chờ ADX giảm xuống < 20 (xu hướng yếu đi) hoặc +DI cắt lên trên -DI trước khi cân nhắc mua."
        })

    # Vortex Indicator
    if last['trend_vortex_ind_pos'] > last['trend_vortex_ind_neg']:
        signals.append({
            'signal': "Vortex Indicator Bullish",
            'explanation': "VORTEX TĂNG GIÁ - DÒNG CHẢY GIÁ HƯỚNG LÊN. Vortex Indicator đo lường chuyển động xoáy (vortex) của giá, xác định điểm bắt đầu và kết thúc xu hướng. Khi VI+ > VI-, dòng chảy giá đang hướng lên, xu hướng tăng đang hoạt động (tín hiệu MUA). Đặc biệt mạnh khi hai đường mới cắt nhau."
        })
    
    if last['trend_vortex_ind_neg'] > last['trend_vortex_ind_pos']:
        signals.append({
            'signal': "Vortex Indicator Bearish",
            'explanation': "VORTEX GIẢM GIÁ - DÒNG CHẢY GIÁ HƯỚNG XUỐNG. Khi VI- > VI+, dòng chảy giá đang hướng xuống, xu hướng giảm đang hoạt động (tín hiệu BÁN). Nên tránh mua hoặc đặt stop-loss chặt."
        })

    # TRIX
    if last['trend_trix'] > 0 and prev['trend_trix'] < 0:
        signals.append({
            'signal': "TRIX Bullish Crossover",
            'explanation': "TRIX CẮT TĂNG - XU HƯỚNG DÀI HẠN CHUYỂN TÍCH CỰC. TRIX sử dụng làm mượt 3 lần để loại bỏ nhiễu và dao động ngắn hạn, chỉ bắt xu hướng thực sự. Khi TRIX vượt qua 0 từ dưới lên, đây là tín hiệu MUA mạnh cho xu hướng trung-dài hạn. Ít bị tín hiệu giả hơn các chỉ báo khác, thích hợp cho nhà đầu tư không muốn giao dịch quá thường xuyên."
        })
    
    if last['trend_trix'] < 0 and prev['trend_trix'] > 0:
        signals.append({
            'signal': "TRIX Bearish Crossover",
            'explanation': "TRIX CẮT GIẢM - XU HƯỚNG DÀI HẠN CHUYỂN TIÊU CỰC. Khi TRIX cắt xuống dưới 0, xu hướng trung-dài hạn đang chuyển giảm (tín hiệu BÁN). Đây là cảnh báo nghiêm trọng vì TRIX ít khi cho tín hiệu giả."
        })

    # Mass Index
    if last['trend_mass_index'] > 27:
        signals.append({
            'signal': f"Mass Index Reversal Signal ({last['trend_mass_index']:.2f} > 27)",
            'explanation': "MASS INDEX - CẢNH BÁO ĐẢO CHIỀU. Mass Index đo lường độ mở rộng của biên độ giá (high-low range). Khi > 27, biên độ giá đã mở rộng mạnh, báo hiệu khả năng đảo chiều xu hướng cao trong vài ngày tới. KHÔNG CHỈ ĐỊNH HƯỚNG mà chỉ cảnh báo có thể đảo chiều. Cần kết hợp với chỉ báo khác để xác định hướng đảo chiều. Đặc biệt hữu ích để bảo vệ lợi nhuận hoặc chuẩn bị thoát lệnh."
        })

    # KST (Know Sure Thing)
    if last['trend_kst'] > last['trend_kst_sig']:
        signals.append({
            'signal': "KST Bullish Crossover",
            'explanation': "KST CẮT TĂNG - ĐỘNG LỰC ĐA THỜI GIAN TÍCH CỰC. KST kết hợp 4 khung thời gian ROC khác nhau (ngắn đến dài hạn) để tạo ra một chỉ báo động lượng toàn diện. Khi đường KST cắt lên trên đường Signal, động lượng từ nhiều chu kỳ đều chuyển tích cực (tín hiệu MUA mạnh). Đây là xác nhận đáng tin cậy về xu hướng tăng."
        })
    
    if last['trend_kst'] < last['trend_kst_sig']:
        signals.append({
            'signal': "KST Bearish Crossover",
            'explanation': "KST CẮT GIẢM - ĐỘNG LỰC ĐA THỜI GIAN TIÊU CỰC. Khi đường KST cắt xuống dưới đường Signal, động lượng từ nhiều chu kỳ đều chuyển tiêu cực (tín hiệu BÁN). Đây là cảnh báo nghiêm trọng về xu hướng giảm."
        })

    # Parabolic SAR
    if last['trend_psar_up_indicator'] == 1:
        signals.append({
            'signal': "PSAR Bullish Reversal",
            'explanation': "PARABOLIC SAR ĐẢO CHIỀU TĂNG - ĐIỂM STOP-LOSS CHUYỂN LÊN TRÊN. Parabolic SAR (Stop And Reverse) hiển thị các điểm dừng và đảo chiều, như những 'chấm' trên hoặc dưới giá. Khi PSAR chuyển từ trên giá xuống dưới giá (up_indicator = 1), đây là tín hiệu đảo chiều tăng (tín hiệu MUA). Các chấm SAR dưới giá hoạt động như trailing stop-loss động, bảo vệ lợi nhuận khi giá tăng."
        })
    
    if last['trend_psar_down_indicator'] == 1:
        signals.append({
            'signal': "PSAR Bearish Reversal",
            'explanation': "PARABOLIC SAR ĐẢO CHIỀU GIẢM - ĐIỂM STOP-LOSS CHUYỂN XUỐNG DƯỚI. Khi PSAR chuyển từ dưới giá lên trên giá (down_indicator = 1), đây là tín hiệu đảo chiều giảm (tín hiệu BÁN). Nên thoát lệnh ngay hoặc đặt lệnh short. Các chấm SAR trên giá hoạt động như kháng cự động."
        })

    # SMA (Simple Moving Average)
    if last['Close'] > last['trend_sma_fast'] and last['trend_sma_fast'] > last['trend_sma_slow']:
        signals.append({
            'signal': f"SMA Fast = {last['trend_sma_fast']:.2f} > Slow Bullish = {last['trend_sma_slow']:.2f}",
            'explanation': "SMA TĂNG GIÁ - CẤU TRÚC HOÀN HẢO. SMA (Đường trung bình động đơn giản) là trung bình giá trong một khoảng thời gian. Khi có cấu trúc: Giá > SMA nhanh > SMA chậm, đây là 'Golden Alignment' - tín hiệu MUA/GIỮ cực mạnh. Tất cả các khung thời gian đều đang tăng, xu hướng rất khỏe mạnh. SMA chậm hoạt động như hỗ trợ chính."
        })
    
    if last['Close'] < last['trend_sma_fast'] and last['trend_sma_fast'] < last['trend_sma_slow']:
        signals.append({
            'signal': f"SMA Fast = {last['trend_sma_fast']:.2f} < Slow Bearish = {last['trend_sma_slow']:.2f}",
            'explanation': "SMA GIẢM GIÁ - CẤU TRÚC TIÊU CỰC. Khi có cấu trúc: Giá < SMA nhanh < SMA chậm, đây là 'Death Alignment' - tín hiệu BÁN/TRÁNH cực mạnh. Tất cả các khung thời gian đều đang giảm, xu hướng xuống rất mạnh. SMA chậm hoạt động như kháng cự chính, khó vượt qua."
        })

    # EMA (Exponential Moving Average)
    if last['Close'] > last['trend_ema_fast'] and last['trend_ema_fast'] > last['trend_ema_slow']:
        signals.append({
            'signal': f"EMA Fast = {last['trend_ema_fast']:.2f} > Slow Bullish = {last['trend_ema_slow']:.2f}",
            'explanation': "EMA TĂNG GIÁ - ĐỘNG LỰC NHANH TÍCH CỰC. EMA (Đường trung bình động mũ) nhạy hơn SMA vì cho trọng số cao hơn cho giá gần đây. Cấu trúc Giá > EMA nhanh > EMA chậm cho thấy động lượng tăng đang tăng tốc (tín hiệu MUA/GIỮ). EMA tốt hơn SMA trong việc bắt xu hướng sớm nhưng có nhiều tín hiệu giả hơn trong thị trường sideway."
        })
    
    if last['Close'] < last['trend_ema_fast'] and last['trend_ema_fast'] < last['trend_ema_slow']:
        signals.append({
            'signal': f"EMA Fast = {last['trend_ema_fast']:.2f} < Slow Bearish = {last['trend_ema_slow']:.2f}",
            'explanation': "EMA GIẢM GIÁ - ĐỘNG LỰC NHANH TIÊU CỰC. Cấu trúc Giá < EMA nhanh < EMA chậm cho thấy động lượng giảm đang tăng tốc (tín hiệu BÁN/TRÁNH). Xu hướng giảm đang mạnh lên, nên đứng ngoài hoặc short."
        })

    # ==================== VOLATILITY INDICATORS ====================
    # Bollinger Bands
    if last['Close'] > last['volatility_bbh']:
        signals.append({
            'signal': "Bollinger Band Upper Breakout",
            'explanation': "BOLLINGER BAND - PHÁ VỠ BĂNG TRÊN. Bollinger Bands tạo ra một 'kênh' xung quanh đường trung bình, rộng khi biến động cao, hẹp khi biến động thấp. Khi giá PHÁ VỠ băng trên, đây có thể là: (1) Tín hiệu MUA mạnh nếu có khối lượng lớn - giá đang bứt phá, hoặc (2) Cảnh báo quá mua - có thể pullback. Trong xu hướng tăng mạnh, giá có thể 'đi dọc' băng trên. Cần xem ngữ cảnh: breakout với volume cao = tích cực, không volume = cảnh báo."
        })
    
    if last['Close'] < last['volatility_bbl']:
        signals.append({
            'signal': "Bollinger Band Lower Breakdown",
            'explanation': "BOLLINGER BAND - PHÁ VỠ BĂNG DƯỚI. Khi giá PHÁ VỠ băng dưới: (1) Có thể là tín hiệu quá bán - cơ hội MUA đáy cho trader mạo hiểm, hoặc (2) Cảnh báo xu hướng giảm mạnh - nên tránh xa. Trong xu hướng giảm mạnh, giá có thể 'đi dọc' băng dưới. Thường xuyên breakout băng dưới = thị trường yếu, cần cẩn trọng."
        })

    # Keltner Channel
    if last['Close'] > last['volatility_kch']:
        signals.append({
            'signal': "Keltner Channel Upper Breakout",
            'explanation': "KELTNER CHANNEL - PHÁ VỠ KÊNH TRÊN. Keltner Channel tương tự Bollinger nhưng dựa trên ATR (True Range) thay vì độ lệch chuẩn, nên ổn định hơn và ít bị breakout giả. Khi giá vượt kênh trên, đây là tín hiệu xu hướng tăng MẠNH đang hình thành (tín hiệu MUA/GIỮ). Đáng tin cậy hơn Bollinger trong việc xác nhận breakout thật."
        })
    
    if last['Close'] < last['volatility_kcl']:
        signals.append({
            'signal': "Keltner Channel Lower Breakdown",
            'explanation': "KELTNER CHANNEL - PHÁ VỠ KÊNH DƯỚI. Khi giá phá vỡ kênh dưới, đây là tín hiệu xu hướng giảm MẠNH (tín hiệu BÁN/TRÁNH). Vì Keltner ít bị breakout giả, đây là cảnh báo nghiêm trọng cần chú ý."
        })

    # Donchian Channel
    if last['Close'] > last['volatility_dch']:
        signals.append({
            'signal': "Donchian Channel Upper Breakout",
            'explanation': "DONCHIAN CHANNEL - ĐẠT ĐỈNH MỚI. Donchian Channel được tạo bởi mức cao nhất và thấp nhất trong N ngày. Khi giá PHÁ VỠ mức cao nhất, đây là 'ĐỈNH MỚI' trong chu kỳ - tín hiệu MUA/GIỮ rất mạnh theo chiến lược Turtle Trading nổi tiếng. Giá đang trong xu hướng tăng rõ ràng, không có kháng cự gần đây. Thường là điểm entry tốt cho trend following."
        })
    
    if last['Close'] < last['volatility_dcl']:
        signals.append({
            'signal': "Donchian Channel Lower Breakdown",
            'explanation': "DONCHIAN CHANNEL - PHÁ ĐÁY MỚI. Khi giá phá vỡ mức thấp nhất trong chu kỳ, đây là 'ĐÁY MỚI' - tín hiệu BÁN/TRÁNH mạnh. Giá đang trong xu hướng giảm rõ ràng, không có hỗ trợ gần. Nên thoát lệnh hoặc chờ ổn định."
        })

    # ATR (Average True Range)
    if last['volatility_atr'] > prev['volatility_atr'] * 1.5:
        signals.append({
            'signal': "ATR Spike (Volatility Increase)",
            'explanation': "ATR TĂNG ĐỘT BIẾN - BIẾN ĐỘNG PHÁ VỠ. ATR đo lường độ biến động trung bình của giá. Khi ATR tăng >50% so với trước đó, thị trường đang trải qua BIẾN ĐỘNG BẤT THƯỜNG. Điều này có thể báo hiệu: (1) Tin tức quan trọng vừa ra, (2) Breakout/breakdown mạnh đang xảy ra, (3) Panic buying/selling, hoặc (4) Đảo chiều xu hướng. Cần TĂNG CẢNH GIÁC, mở rộng stop-loss để tránh bị quét, hoặc giảm kích thước lệnh. Biến động cao = rủi ro cao."
        })
    
    # Ulcer Index
    if last['volatility_ui'] > 20:
        signals.append({
            'signal': f"Ulcer Index High Risk ({last['volatility_ui']:.2f} > 20)",
            'explanation': "ULCER INDEX - RỦI RO GIẢM GIÁ CAO. Ulcer Index đo lường 'nỗi đau' của nhà đầu tư từ việc giá giảm so với đỉnh gần nhất. Khác với ATR đo cả hai chiều, UI chỉ đo rủi ro GIẢM. Khi UI > 20, thị trường đang trải qua những đợt giảm sâu và kéo dài, gây 'đau đầu' cho nhà đầu tư (như đau dạ dày - ulcer). Đây là cảnh báo RỦI RO CAO, nên giảm kích thước vị thế hoặc đứng ngoài cho đến khi UI giảm xuống."
        })

    # ==================== VOLUME INDICATORS ====================
    # OBV (On-Balance Volume)
    if last['volume_obv'] > prev['volume_obv'] and last['Close'] > prev['Close']:
        signals.append({
            'signal': "OBV Increasing with Price",
            'explanation': "OBV TĂNG CÙNG GIÁ - XÁC NHẬN DÒNG TIỀN VÀO. OBV tích lũy khối lượng: cộng volume khi giá tăng, trừ volume khi giá giảm. Khi OBV tăng cùng với giá tăng, có nghĩa là 'tiền thông minh' đang mua vào, xác nhận xu hướng tăng là THẬT (tín hiệu MUA/GIỮ mạnh). Đây là dấu hiệu khối lượng hỗ trợ đà tăng giá, không phải pump giả. Nếu giá tăng nhưng OBV giảm = cảnh báo phân kỳ, xu hướng yếu."
        })
    
    # CMF (Chaikin Money Flow)
    if last['volume_cmf'] > 0.1:
        signals.append({
            'signal': f"Positive Chaikin Money Flow ({last['volume_cmf']:.2f} > 0.1)",
            'explanation': "CMF DƯƠNG - DÒNG TIỀN TÍCH CỰC. CMF đo lường áp lực mua/bán dựa trên vị trí giá đóng cửa trong range và khối lượng. CMF > 0.1 nghĩa là giá thường đóng cửa gần mức cao nhất trong ngày VÀ có khối lượng lớn - dấu hiệu áp lực MUA mạnh và 'tiền thông minh' đang tích lũy (tín hiệu MUA). CMF > 0.2 là rất mạnh. CMF < -0.1 = áp lực bán."
        })
    
    # Force Index
    if last['volume_fi'] > 0 and prev['volume_fi'] < 0:
        signals.append({
            'signal': "Force Index Bullish Crossover",
            'explanation': "FORCE INDEX CẮT TĂNG - SỨC MẠNH MUA QUAY LẠI. Force Index kết hợp giá và khối lượng để đo 'sức mạnh' của từng cây nến. Khi Force Index chuyển từ âm sang dương, sức mạnh mua đang vượt qua sức mạnh bán (tín hiệu MUA). Đặc biệt mạnh nếu kèm khối lượng lớn. Chỉ báo này tốt để xác nhận breakout hay false breakout."
        })
    
    # VPT (Volume Price Trend)
    if last['volume_vpt'] > prev['volume_vpt']:
        signals.append({
            'signal': "Volume Price Trend Increasing",
            'explanation': "VPT TĂNG - KHỐI LƯỢNG HỖ TRỢ GIÁ. VPT tương tự OBV nhưng cộng/trừ khối lượng theo TỶ LỆ % thay đổi giá, nên nhạy hơn với biến động nhỏ. VPT tăng nghĩa là dòng khối lượng đang hỗ trợ xu hướng tăng giá (tín hiệu MUA/GIỮ). Nếu giá tăng nhưng VPT giảm = phân kỳ, cảnh báo xu hướng suy yếu."
        })
    
    # MFI (Money Flow Index)
    if last['volume_mfi'] > 80:
        signals.append({
            'signal': f"Money Flow Index Overbought ({last['volume_mfi']:.2f} > 80)",
            'explanation': "MFI QUÁ MUA - DÒNG TIỀN QUÁ TẢI. MFI được gọi là 'RSI có khối lượng', đo lường áp lực mua/bán kết hợp giá và volume. MFI > 80 nghĩa là dòng tiền mua đã quá mạnh trong thời gian ngắn, thị trường có thể cần 'hạ nhiệt' (cảnh báo BÁN hoặc giảm vị thế). Tuy nhiên trong uptrend mạnh, MFI có thể ở trạng thái overbought kéo dài."
        })
    
    if last['volume_mfi'] < 20:
        signals.append({
            'signal': f"Money Flow Index Oversold ({last['volume_mfi']:.2f} < 20)",
            'explanation': "MFI QUÁ BÁN - DÒNG TIỀN CẠN KIỆT. MFI < 20 nghĩa là áp lực bán đã quá lớn, dòng tiền đang cạn kiệt, có thể sắp đảo chiều (tín hiệu MUA tiềm năng). Đây là vùng oversold có xét đến khối lượng, đáng tin cậy hơn RSI đơn thuần."
        })
    
    # NVI (Negative Volume Index)
    if last['volume_nvi'] > prev['volume_nvi']:
        signals.append({
            'signal': "Negative Volume Index Bullish",
            'explanation': "NVI TĂNG - TIỀN THÔNG MINH TÍCH LŨY. NVI chỉ thay đổi khi khối lượng GIẢM so với ngày trước, theo lý thuyết 'tiền thông minh' giao dịch khi volume thấp (tránh chú ý). NVI tăng nghĩa là trong những phiên volume thấp, giá vẫn tăng - dấu hiệu tích lũy lặng lẽ của tổ chức (tín hiệu MUA dài hạn). NVI là chỉ báo dài hạn, không dùng cho trading ngắn."
        })

    # ==================== OTHERS ====================
    # Daily Return
    if last['others_dr'] > 2:
        signals.append({
            'signal': f"Daily Return Bullish ({(last['others_dr']*100):.2f}% > 2%)",
            'explanation': "LỢI NHUẬN NGÀY MẠNH - TĂNG NÓNG. Daily Return (DR) đo lường % thay đổi giá trong ngày. DR > 2% nghĩa là giá tăng >2% trong một ngày - đây là mức tăng đáng kể, cho thấy động lượng mua rất mạnh (tín hiệu tích cực). Tuy nhiên cần cẩn trọng: tăng quá nóng có thể dẫn đến pullback ngắn hạn. DR > 5% trong một ngày = tăng 'nóng bỏng tay', cần có kế hoạch chốt lời."
        })
    
    # Cumulative Return
    if last['others_cr'] > 0:
        signals.append({
            'signal': "Cumulative Return Positive",
            'explanation': "LỢI NHUẬN TÍCH LŨY DƯƠNG - ĐANG LỜI. Cumulative Return (CR) đo tổng lợi nhuận từ điểm bắt đầu tính. CR > 0 nghĩa là nếu bạn mua từ điểm bắt đầu, bạn đang có lãi (tín hiệu tích cực). CR càng cao càng tốt, nhưng cần xem trend: nếu CR đang giảm dần dù vẫn dương = xu hướng đang yếu đi."
        })

    # ==================== RISK MANAGEMENT ====================
    # ATR-based Stop Loss and Take Profit
    if last['volatility_atr'] > 0:
        stop_loss = last['Close'] - 2 * last['volatility_atr']
        take_profit = last['Close'] + 3 * last['volatility_atr']
        signals.append({
            'signal': f"Risk Management: Stop-Loss={stop_loss:.2f}, Take-Profit={take_profit:.2f}",
            'explanation': f"QUẢN TRỊ RỦI RO DỰA TRÊN ATR. ATR hiện tại = {last['volatility_atr']:.2f}. Stop-Loss được đặt ở 2xATR dưới giá hiện tại (cho phép giá dao động bình thường mà không bị quét). Take-Profit ở 3xATR trên giá hiện tại (tỷ lệ Risk:Reward = 1:1.5). Đây là cách đặt lệnh ĐỘNG, tự điều chỉnh theo biến động thị trường: ATR cao (biến động lớn) = stop-loss rộng hơn để tránh bị quét sớm; ATR thấp = stop-loss chặt hơn. Luôn tuân thủ stop-loss để bảo vệ vốn!"
        })

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