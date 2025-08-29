import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from data_loader import load_financials_yf  # Assume this exists

def calc_financial_ratios(fin: pd.DataFrame, bs: pd.DataFrame, cf: pd.DataFrame, price: float) -> Dict[str, Optional[float]]:
    """Calculate comprehensive financial ratios using provided column names"""
    ratios = {}
    
    # Profitability Ratios
    try:
        ratios['roe'] = (fin['Net Income'] / bs['Stockholders Equity']).mean()
    except: ratios['roe'] = None
    try:
        ratios['roa'] = (fin['Net Income'] / bs['Total Assets']).mean()
    except: ratios['roa'] = None
    try:
        ratios['gross_margin'] = (fin['Gross Profit'] / fin['Total Revenue']).mean()
    except: ratios['gross_margin'] = None
    try:
        ratios['operating_margin'] = (fin['Operating Income'] / fin['Total Revenue']).mean()
    except: ratios['operating_margin'] = None

    # Leverage Ratios
    try:
        ratios['debt_equity'] = (bs['Total Liabilities Net Minority Interest'] / bs['Stockholders Equity']).mean()
    except: ratios['debt_equity'] = None
    try:
        ratios['interest_coverage'] = (fin['EBIT'] / fin['Interest Expense']).mean()
    except: ratios['interest_coverage'] = None

    # Liquidity Ratios
    try:
        ratios['current_ratio'] = (bs['Current Assets'] / bs['Current Liabilities']).mean()
    except: ratios['current_ratio'] = None
    try:
        ratios['quick_ratio'] = ((bs['Current Assets'] - bs['Inventory']) / 
                               bs['Current Liabilities']).mean()
    except: ratios['quick_ratio'] = None

    # Efficiency Ratios
    try:
        ratios['asset_turnover'] = (fin['Total Revenue'] / bs['Total Assets']).mean()
    except: ratios['asset_turnover'] = None
    try:
        ratios['inventory_turnover'] = (fin['Cost Of Revenue'] / bs['Inventory']).mean()
    except: ratios['inventory_turnover'] = None

    # Cash Flow Ratios
    try:
        ratios['cfo_ni'] = (cf['Operating Cash Flow'] / fin['Net Income']).mean()
    except: ratios['cfo_ni'] = None
    try:
        ratios['free_cash_flow'] = (cf['Free Cash Flow'] / fin['Net Income']).mean()
    except: ratios['free_cash_flow'] = None

    # Valuation Ratios
    try:
        shares_outstanding = bs['Ordinary Shares Number']
        ratios['pe_ratio'] = price / (fin['Net Income'] / shares_outstanding).mean()
    except: ratios['pe_ratio'] = None
    try:
        ratios['pb_ratio'] = price / (bs['Stockholders Equity'] / bs['Ordinary Shares Number']).mean()
    except: ratios['pb_ratio'] = None

    return ratios

def calc_beneish_m_score(fin: pd.DataFrame, bs: pd.DataFrame, cf: pd.DataFrame) -> Optional[float]:
    """Calculate full Beneish M-Score using provided column names"""

    # Days Sales in Receivables Index
    dsri = ((bs['Receivables'] / fin['Total Revenue']).shift(-1) / 
            (bs['Receivables'] / fin['Total Revenue'])).mean()
    
    # Gross Margin Index
    gmi = ((fin['Gross Profit'].shift(-1) / fin['Total Revenue'].shift(-1)) / 
            (fin['Gross Profit'] / fin['Total Revenue'])).mean()
    
    # Asset Quality Index
    aqi = (((bs['Total Assets'] - bs['Current Assets'] - bs['Net PPE']) / 
            bs['Total Assets']).shift(-1) /
            ((bs['Total Assets'] - bs['Current Assets'] - bs['Net PPE']) / 
            bs['Total Assets'])).mean()
    
    # Sales Growth Index
    sgi = (fin['Total Revenue'].shift(-1) / fin['Total Revenue']).mean()
    
    # Depreciation Index
    depi = ((cf['Depreciation'] / (cf['Depreciation'] + bs['Net PPE'])).shift(-1) /
            (cf['Depreciation'] / (cf['Depreciation'] + bs['Net PPE']))).mean()
    
    # Sales, General and Administrative Expenses Index
    sgai = ((fin['Selling General And Administration'] / fin['Total Revenue']).shift(-1) /
            (fin['Selling General And Administration'] / fin['Total Revenue'])).mean()
    
    # Leverage Index
    lvgi = ((bs['Total Liabilities Net Minority Interest'] / bs['Total Assets']).shift(-1) /
            (bs['Total Liabilities Net Minority Interest'] / bs['Total Assets'])).mean()
    
    # Total Accruals to Total Assets
    tata = ((fin['Net Income'] - cf['Operating Cash Flow']) / 
            bs['Total Assets']).mean()

    # M-Score formula
    m_score = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 
                0.892 * sgi + 0.115 * depi - 0.172 * sgai + 
                4.679 * tata - 0.327 * lvgi)
    return m_score
    

def normalize_score(value: float, benchmark: float, range_min: float, range_max: float) -> float:
    """Normalize ratio scores to 0-100 scale"""
    if value is None or np.isnan(value):
        return 0
    normalized = (value - range_min) / (range_max - range_min) * 100
    return max(0, min(100, normalized))

def score_stock(ticker: str, price: float) -> Dict:
    """Advanced stock scoring with weighted metrics"""
    fin, bs, cf = load_financials_yf(ticker)
    fin = fin.T
    bs = bs.T
    cf = cf.T
  
    ratios = calc_financial_ratios(fin, bs, cf, price)
    beneish = calc_beneish_m_score(fin, bs, cf)

    # Weighted scoring system
    weights = {
        'roe': 0.15, 'roa': 0.10, 'gross_margin': 0.08, 'operating_margin': 0.08,
        'debt_equity': 0.10, 'interest_coverage': 0.07, 'current_ratio': 0.07,
        'quick_ratio': 0.07, 'asset_turnover': 0.05, 'inventory_turnover': 0.05,
        'cfo_ni': 0.08, 'free_cash_flow': 0.08, 'pe_ratio': 0.05, 'pb_ratio': 0.05,
        'beneish': 0.12
    }

    score = 0
    # Profitability
    if ratios['roe']: score += normalize_score(ratios['roe'], 0.15, 0, 0.5) * weights['roe']
    if ratios['roa']: score += normalize_score(ratios['roa'], 0.08, 0, 0.25) * weights['roa']
    if ratios['gross_margin']: score += normalize_score(ratios['gross_margin'], 0.3, 0, 0.7) * weights['gross_margin']
    if ratios['operating_margin']: score += normalize_score(ratios['operating_margin'], 0.15, 0, 0.4) * weights['operating_margin']

    # Leverage
    if ratios['debt_equity']: score += (100 - normalize_score(ratios['debt_equity'], 1, 0, 3)) * weights['debt_equity']
    if ratios['interest_coverage']: score += normalize_score(ratios['interest_coverage'], 3, 0, 10) * weights['interest_coverage']

    # Liquidity
    if ratios['current_ratio']: score += normalize_score(ratios['current_ratio'], 1.5, 0, 3) * weights['current_ratio']
    if ratios['quick_ratio']: score += normalize_score(ratios['quick_ratio'], 1, 0, 2) * weights['quick_ratio']

    # Efficiency
    if ratios['asset_turnover']: score += normalize_score(ratios['asset_turnover'], 1, 0, 2) * weights['asset_turnover']
    if ratios['inventory_turnover']: score += normalize_score(ratios['inventory_turnover'], 5, 0, 15) * weights['inventory_turnover']

    # Cash Flow
    if ratios['cfo_ni']: score += normalize_score(ratios['cfo_ni'], 1, 0, 3) * weights['cfo_ni']
    if ratios['free_cash_flow']: score += normalize_score(ratios['free_cash_flow'], 0.5, 0, 2) * weights['free_cash_flow']

    # Valuation
    if ratios['pe_ratio']: score += (100 - normalize_score(ratios['pe_ratio'], 15, 0, 50)) * weights['pe_ratio']
    if ratios['pb_ratio']: score += (100 - normalize_score(ratios['pb_ratio'], 2, 0, 5)) * weights['pb_ratio']

    # Beneish M-Score (lower is better)
    if beneish: score += (100 - normalize_score(beneish, -2.2, -3, 0)) * weights['beneish']

    return {
        "ticker": ticker,
        "score": round(score, 2),
        "ratios": {k: round(v, 4) if v is not None else None for k, v in ratios.items()},
        "beneish_m_score": round(beneish, 4) if beneish is not None else None
    }

def rank_stocks(tickers: list, prices: Dict[str, float]) -> pd.DataFrame:
    """Rank multiple stocks based on scores"""
    results = []
    for ticker in tickers:
        result = score_stock(ticker, prices.get(ticker, 100))  # Default price if not provided
        results.append(result)
    
    df = pd.DataFrame(results)
    df = df.sort_values(by='score', ascending=False)
    df['rank'] = range(1, len(df) + 1)
    return df

if __name__ == "__main__":
    # Example usage
    tickers = ["BID.VN"]
    prices = {"BID.VN": 55.6}
    rankings = rank_stocks(tickers, prices)
    print(rankings)