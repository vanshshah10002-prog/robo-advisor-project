import json
import os

REGISTRY_PATH = os.path.join("backend", "data", "uk_etf_registry.json")

INDIAN_ETFS = [
    # US / Global Arbitrage explicitly requested
    {"ticker": "MON100.NS", "name": "Motilal Oswal NASDAQ 100 ETF", "asset_class": "indian_arbitrage_us_tech", "expense_ratio": 0.0058},
    {"ticker": "MASPT50.NS", "name": "Mirae Asset S&P 500 Top 50 ETF", "asset_class": "indian_arbitrage_us_equity", "expense_ratio": 0.0050},
    {"ticker": "MAFANG.NS", "name": "Mirae Asset NYSE FANG+ ETF", "asset_class": "indian_arbitrage_us_tech", "expense_ratio": 0.0050},
    {"ticker": "MONQ50.NS", "name": "Motilal Oswal NASDAQ Q50 ETF", "asset_class": "indian_arbitrage_us_tech", "expense_ratio": 0.0050},
    
    # Large Cap (Nifty 50 & Nifty Next 50)
    {"ticker": "NIFTYBEES.NS", "name": "Nippon India ETF Nifty 50 BeES", "asset_class": "indian_large_cap", "expense_ratio": 0.0005},
    {"ticker": "SETFNIF50.NS", "name": "SBI Nifty 50 ETF", "asset_class": "indian_large_cap", "expense_ratio": 0.0007},
    {"ticker": "UTINIFTETF.NS", "name": "UTI Nifty 50 ETF", "asset_class": "indian_large_cap", "expense_ratio": 0.0007},
    {"ticker": "ICICINIFTY.NS", "name": "ICICI Prudential Nifty ETF", "asset_class": "indian_large_cap", "expense_ratio": 0.0005},
    {"ticker": "KOTAKNIFTY.NS", "name": "Kotak Nifty 50 ETF", "asset_class": "indian_large_cap", "expense_ratio": 0.0010},
    {"ticker": "BSLNIFTY.NS", "name": "Aditya Birla Sun Life Nifty ETF", "asset_class": "indian_large_cap", "expense_ratio": 0.0010},
    {"ticker": "HDFCNIFTY.NS", "name": "HDFC Nifty 50 ETF", "asset_class": "indian_large_cap", "expense_ratio": 0.0005},
    {"ticker": "JUNIORBEES.NS", "name": "Nippon India ETF Nifty Next 50", "asset_class": "indian_large_cap", "expense_ratio": 0.0015},
    {"ticker": "SETFNN50.NS", "name": "SBI ETF Nifty Next 50", "asset_class": "indian_large_cap", "expense_ratio": 0.0015},
    {"ticker": "ICICINXT50.NS", "name": "ICICI Prudential Nifty Next 50 ETF", "asset_class": "indian_large_cap", "expense_ratio": 0.0015},
    
    # Mid & Small Cap
    {"ticker": "MID150BEES.NS", "name": "Nippon India ETF Nifty Midcap 150", "asset_class": "indian_mid_cap", "expense_ratio": 0.0021},
    {"ticker": "MOM100.NS", "name": "Motilal Oswal Midcap 100 ETF", "asset_class": "indian_mid_cap", "expense_ratio": 0.0020},
    {"ticker": "HDFCMID150.NS", "name": "HDFC Nifty Midcap 150 ETF", "asset_class": "indian_mid_cap", "expense_ratio": 0.0020},
    {"ticker": "ICICIMCAP.NS", "name": "ICICI Prudential Midcap 150 ETF", "asset_class": "indian_mid_cap", "expense_ratio": 0.0020},
    {"ticker": "SMALLCAP.NS", "name": "Motilal Oswal Nifty Smallcap 250 ETF", "asset_class": "indian_small_cap", "expense_ratio": 0.0030},
    {"ticker": "HDFCSML250.NS", "name": "HDFC Nifty Smallcap 250 ETF", "asset_class": "indian_small_cap", "expense_ratio": 0.0030},

    # Broad Market Multi-Cap
    {"ticker": "NIFTY100.NS", "name": "Kotak Nifty 100 ETF", "asset_class": "indian_broad_equity", "expense_ratio": 0.0015},
    {"ticker": "ICICIM150.NS", "name": "ICICI Prudential Multicap 150 ETF", "asset_class": "indian_broad_equity", "expense_ratio": 0.0020},

    # Smart Beta / Factors
    {"ticker": "NV20IETF.NS", "name": "Nippon India ETF Nifty 50 Value 20", "asset_class": "indian_factor_value", "expense_ratio": 0.0031},
    {"ticker": "KOTAKNV20.NS", "name": "Kotak Nifty 50 Value 20 ETF", "asset_class": "indian_factor_value", "expense_ratio": 0.0030},
    {"ticker": "MOMOMENTUM.NS", "name": "Motilal Oswal Nifty 200 Momentum 30", "asset_class": "indian_factor_momentum", "expense_ratio": 0.0032},
    {"ticker": "ICICIMOM30.NS", "name": "ICICI Prudential Nifty 200 Momentum 30 ETF", "asset_class": "indian_factor_momentum", "expense_ratio": 0.0032},
    {"ticker": "LOWVOLIETF.NS", "name": "ICICI Prudential Nifty 100 Low Volatility 30 ETF", "asset_class": "indian_factor_low_vol", "expense_ratio": 0.0030},
    {"ticker": "HDFCLOWVOL.NS", "name": "HDFC Nifty 100 Low Volatility 30 ETF", "asset_class": "indian_factor_low_vol", "expense_ratio": 0.0030},
    {"ticker": "DIVOPPBEES.NS", "name": "Nippon India ETF Nifty Dividend Opportunities 50", "asset_class": "indian_factor_dividend", "expense_ratio": 0.0035},

    # Sectoral - Financials
    {"ticker": "BANKBEES.NS", "name": "Nippon India ETF Nifty Bank", "asset_class": "indian_sector_financials", "expense_ratio": 0.0016},
    {"ticker": "SETFBANK.NS", "name": "SBI ETF Nifty Bank", "asset_class": "indian_sector_financials", "expense_ratio": 0.0016},
    {"ticker": "KOTAKBKETF.NS", "name": "Kotak Nifty Bank ETF", "asset_class": "indian_sector_financials", "expense_ratio": 0.0015},
    {"ticker": "ICICIBANKP.NS", "name": "ICICI Prudential Nifty Private Bank ETF", "asset_class": "indian_sector_financials", "expense_ratio": 0.0016},
    {"ticker": "PSUBNKBEES.NS", "name": "Nippon India ETF Nifty PSU Bank", "asset_class": "indian_sector_financials", "expense_ratio": 0.0017},

    # Sectoral - IT & Infra & Others
    {"ticker": "ITBEES.NS", "name": "Nippon India ETF Nifty IT", "asset_class": "indian_sector_it", "expense_ratio": 0.0022},
    {"ticker": "SETFIT.NS", "name": "SBI ETF Nifty IT", "asset_class": "indian_sector_it", "expense_ratio": 0.0022},
    {"ticker": "ICICIIT.NS", "name": "ICICI Prudential Nifty IT ETF", "asset_class": "indian_sector_it", "expense_ratio": 0.0022},
    {"ticker": "PHARMABEES.NS", "name": "Nippon India ETF Nifty Pharma", "asset_class": "indian_sector_healthcare", "expense_ratio": 0.0022},
    {"ticker": "ICICIPHARM.NS", "name": "ICICI Prudential Nifty Pharma ETF", "asset_class": "indian_sector_healthcare", "expense_ratio": 0.0023},
    {"ticker": "CONSUMBEES.NS", "name": "Nippon India ETF Nifty FMCG", "asset_class": "indian_sector_fmcg", "expense_ratio": 0.0023},
    {"ticker": "ICICIFMCG.NS", "name": "ICICI Prudential Nifty FMCG ETF", "asset_class": "indian_sector_fmcg", "expense_ratio": 0.0023},
    {"ticker": "AUTOBEES.NS", "name": "Nippon India ETF Nifty Auto", "asset_class": "indian_sector_auto", "expense_ratio": 0.0023},
    {"ticker": "INFRABEES.NS", "name": "Nippon India ETF Nifty Infrastructure", "asset_class": "indian_sector_infra", "expense_ratio": 0.0023},
    {"ticker": "MAKEINDIA.NS", "name": "ICICI Prudential Nifty India Manufacturing ETF", "asset_class": "indian_sector_manufacturing", "expense_ratio": 0.0025},
    {"ticker": "CPSEETF.NS", "name": "CPSE ETF", "asset_class": "indian_sector_psu", "expense_ratio": 0.0001},
    {"ticker": "BHARAT22.NS", "name": "Bharat 22 ETF", "asset_class": "indian_sector_psu", "expense_ratio": 0.0001},

    # Commodities (Gold & Silver)
    {"ticker": "GOLDBEES.NS", "name": "Nippon India ETF Gold BeES", "asset_class": "indian_gold", "expense_ratio": 0.0079},
    {"ticker": "SETFGOLD.NS", "name": "SBI ETF Gold", "asset_class": "indian_gold", "expense_ratio": 0.0065},
    {"ticker": "HDFCGOLD.NS", "name": "HDFC Gold ETF", "asset_class": "indian_gold", "expense_ratio": 0.0060},
    {"ticker": "SILVERBEES.NS", "name": "Nippon India Silver ETF", "asset_class": "indian_silver", "expense_ratio": 0.0050},
    {"ticker": "ICICISILVE.NS", "name": "ICICI Prudential Silver ETF", "asset_class": "indian_silver", "expense_ratio": 0.0050},

    # Debt / Government Bonds
    {"ticker": "GILTBEES.NS", "name": "Nippon India ETF Nifty 8-13 yr G-Sec", "asset_class": "indian_bonds", "expense_ratio": 0.0016},
    {"ticker": "LICNETFGSC.NS", "name": "LIC MF Nifty 8-13 yr G-Sec ETF", "asset_class": "indian_bonds", "expense_ratio": 0.0016},
    {"ticker": "SETF10GILT.NS", "name": "SBI ETF 10 Year Gilt", "asset_class": "indian_bonds", "expense_ratio": 0.0015},
]

def main():
    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    
    # ensure it's a list
    if not isinstance(registry, list):
        if "etfs" in registry:
            registry = registry["etfs"]
        else:
            registry = []

    # Map existing tickers to avoid duplicates
    existing_tickers = {etf['ticker'] for etf in registry}
    added = 0
    for new_etf in INDIAN_ETFS:
        if new_etf['ticker'] not in existing_tickers:
            # fill in default missing fields
            new_etf['currency'] = "INR"
            new_etf['domicile'] = "India"
            new_etf['ucits'] = False
            new_etf['tlh_substitute'] = None
            new_etf['fund_size_gbp_mm'] = 1000  # Default dummy
            
            registry.append(new_etf)
            added += 1

    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=4)
        
    print(f"Successfully added {added} Indian ETFs to the registry. Total ETFs: {len(registry)}")

if __name__ == "__main__":
    main()
