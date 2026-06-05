"""
Declarative configuration of every data series the dashboard tracks.

Each entry can specify a Yahoo Finance ticker (preferred for daily price data)
and/or a FRED series id (preferred for official macro statistics).
The fetcher tries Yahoo first if present, then falls back to FRED.

Fields:
  id        - stable key used by the frontend
  name      - human label
  region    - geographic tag (US, UK, EU, JP, CN, GLOBAL ...)
  unit      - display unit ($, GBP, %, index, etc.)
  yahoo     - Yahoo ticker (optional)
  fred      - FRED series id (optional)
  freq      - FRED frequency override ("d", "w", "m", "q", "a")
  transform - optional transform: "yoy_pct" computes 12-month YoY pct change
  scale     - optional multiplier applied to every value
  note      - short description for tooltips
"""

SECTIONS = {
    # ───────────────────────────── EQUITY INDICES ─────────────────────────────
    "markets": {
        "title": "Equity Markets",
        "icon": "trending_up",
        "blurb": "Major global stock indices. The pulse of risk appetite.",
        "series": [
            {"id": "sp500",    "name": "S&P 500",            "region": "US", "unit": "pts", "yahoo": "^GSPC",   "fred": "SP500",       "note": "500 large-cap US stocks."},
            {"id": "dow",      "name": "Dow Jones",          "region": "US", "unit": "pts", "yahoo": "^DJI",    "fred": "DJIA",        "note": "30 US blue-chip stocks."},
            {"id": "nasdaq",   "name": "NASDAQ Composite",   "region": "US", "unit": "pts", "yahoo": "^IXIC",   "fred": "NASDAQCOM",   "note": "Tech-heavy US index."},
            {"id": "russell",  "name": "Russell 2000",       "region": "US", "unit": "pts", "yahoo": "^RUT",                           "note": "US small-cap proxy."},
            {"id": "ftse100",  "name": "FTSE 100",           "region": "UK", "unit": "pts", "yahoo": "^FTSE",                          "note": "UK 100 largest listed."},
            {"id": "ftse250",  "name": "FTSE 250",           "region": "UK", "unit": "pts", "yahoo": "^FTMC",                          "note": "UK mid-caps — better UK-economy proxy than FTSE 100."},
            {"id": "dax",      "name": "DAX",                "region": "DE", "unit": "pts", "yahoo": "^GDAXI",                         "note": "Germany 40 blue-chips."},
            {"id": "cac40",    "name": "CAC 40",             "region": "FR", "unit": "pts", "yahoo": "^FCHI",                          "note": "France 40 blue-chips."},
            {"id": "stoxx50",  "name": "Euro Stoxx 50",      "region": "EU", "unit": "pts", "yahoo": "^STOXX50E",                      "note": "Eurozone blue-chip index."},
            {"id": "ibex",     "name": "IBEX 35",            "region": "ES", "unit": "pts", "yahoo": "^IBEX",                          "note": "Spain 35 large-caps."},
            {"id": "nikkei",   "name": "Nikkei 225",         "region": "JP", "unit": "pts", "yahoo": "^N225",                          "note": "Japan 225 large-caps."},
            {"id": "hangseng", "name": "Hang Seng",          "region": "HK", "unit": "pts", "yahoo": "^HSI",                           "note": "Hong Kong large-caps."},
            {"id": "shcomp",   "name": "Shanghai Composite", "region": "CN", "unit": "pts", "yahoo": "000001.SS",                      "note": "China A-shares headline index."},
            {"id": "asx200",   "name": "ASX 200",            "region": "AU", "unit": "pts", "yahoo": "^AXJO",                          "note": "Australia top 200."},
            {"id": "sensex",   "name": "BSE Sensex",         "region": "IN", "unit": "pts", "yahoo": "^BSESN",                         "note": "India 30 large-caps."},
            {"id": "tsx",      "name": "S&P/TSX Composite",  "region": "CA", "unit": "pts", "yahoo": "^GSPTSE",                        "note": "Canada broad equity index."},
            {"id": "bovespa",  "name": "Bovespa",            "region": "BR", "unit": "pts", "yahoo": "^BVSP",                          "note": "Brazil headline index."},
        ],
    },

    # ───────────────────────────── BOND YIELDS ─────────────────────────────
    "bonds": {
        "title": "Bond Yields",
        "icon": "show_chart",
        "blurb": "Sovereign borrowing costs. Bond markets price the future.",
        "series": [
            {"id": "us_2y",   "name": "US 2-Year Treasury",   "region": "US", "unit": "%", "fred": "DGS2",                "note": "Most sensitive to near-term Fed policy."},
            {"id": "us_5y",   "name": "US 5-Year Treasury",   "region": "US", "unit": "%", "fred": "DGS5"},
            {"id": "us_10y",  "name": "US 10-Year Treasury",  "region": "US", "unit": "%", "fred": "DGS10",               "note": "Global risk-free benchmark."},
            {"id": "us_30y",  "name": "US 30-Year Treasury",  "region": "US", "unit": "%", "fred": "DGS30"},
            {"id": "us_10y_real", "name": "US 10-Year Real",  "region": "US", "unit": "%", "fred": "DFII10",              "note": "TIPS yield — real cost of capital."},
            {"id": "uk_10y",  "name": "UK 10-Year Gilt",      "region": "UK", "unit": "%", "fred": "IRLTLT01GBM156N",    "freq": "m"},
            {"id": "de_10y",  "name": "Germany 10-Year Bund", "region": "DE", "unit": "%", "fred": "IRLTLT01DEM156N",    "freq": "m"},
            {"id": "fr_10y",  "name": "France 10-Year OAT",   "region": "FR", "unit": "%", "fred": "IRLTLT01FRM156N",    "freq": "m"},
            {"id": "it_10y",  "name": "Italy 10-Year BTP",    "region": "IT", "unit": "%", "fred": "IRLTLT01ITM156N",    "freq": "m"},
            {"id": "jp_10y",  "name": "Japan 10-Year JGB",    "region": "JP", "unit": "%", "fred": "IRLTLT01JPM156N",    "freq": "m"},
            {"id": "ca_10y",  "name": "Canada 10-Year",       "region": "CA", "unit": "%", "fred": "IRLTLT01CAM156N",    "freq": "m"},
            {"id": "au_10y",  "name": "Australia 10-Year",    "region": "AU", "unit": "%", "fred": "IRLTLT01AUM156N",    "freq": "m"},
            {"id": "curve_10y2y",  "name": "US 10Y-2Y Spread", "region": "US", "unit": "bps", "fred": "T10Y2Y", "scale": 100, "note": "Inversions historically signal recession."},
            {"id": "curve_10y3m",  "name": "US 10Y-3M Spread", "region": "US", "unit": "bps", "fred": "T10Y3M", "scale": 100, "note": "NY Fed's preferred recession gauge."},
        ],
    },

    # ───────────────────────────── POLICY RATES ─────────────────────────────
    "rates": {
        "title": "Central Bank Rates",
        "icon": "account_balance",
        "blurb": "The price of money set by central banks.",
        "series": [
            {"id": "fed_funds",  "name": "US Fed Funds Rate",    "region": "US", "unit": "%", "fred": "FEDFUNDS",        "note": "FOMC policy target (monthly avg)."},
            {"id": "boe_rate",   "name": "UK BoE Bank Rate",     "region": "UK", "unit": "%", "boe_scrape": True,         "note": "Bank of England policy rate, scraped from the BoE IADB Bank-Rate page. Updates within minutes of any MPC decision; 258 change points back to 1975."},
            {"id": "ecb_rate",   "name": "ECB Deposit Rate",     "region": "EU", "unit": "%", "fred": "ECBDFR",          "note": "Eurozone benchmark."},
            {"id": "boj_rate",   "name": "Japan Policy Rate",    "region": "JP", "unit": "%", "fred": "IRSTCB01JPM156N", "note": "Bank of Japan call rate."},
            {"id": "boc_rate",   "name": "Canada Overnight",     "region": "CA", "unit": "%", "fred": "IRSTCB01CAM156N"},
            {"id": "snb_rate",   "name": "Swiss 3-Month Rate",   "region": "CH", "unit": "%", "fred": "IR3TIB01CHM156N"},
            {"id": "rba_rate",   "name": "Australia Discount",   "region": "AU", "unit": "%", "fred": "INTDSRAUM193N"},
            {"id": "sec_overnight", "name": "US SOFR",           "region": "US", "unit": "%", "fred": "SOFR",            "note": "Successor to LIBOR (since 2018)."},
            {"id": "real_rate",  "name": "US Real Fed Funds",    "region": "US", "unit": "%", "fred": "REAINTRATREARAT10Y", "note": "10y real interest rate."},
        ],
    },

    # ───────────────────────────── INFLATION ─────────────────────────────
    "inflation": {
        "title": "Inflation",
        "icon": "local_fire_department",
        "blurb": "Year-over-year change in consumer prices.",
        "series": [
            {"id": "us_cpi_yoy",   "name": "US CPI YoY",           "region": "US", "unit": "%", "fred": "CPIAUCSL",         "transform": "yoy_pct"},
            {"id": "us_core_yoy",  "name": "US Core CPI YoY",      "region": "US", "unit": "%", "fred": "CPILFESL",         "transform": "yoy_pct"},
            {"id": "us_pce_yoy",   "name": "US PCE YoY",           "region": "US", "unit": "%", "fred": "PCEPI",            "transform": "yoy_pct", "note": "Fed's preferred gauge."},
            {"id": "us_core_pce",  "name": "US Core PCE YoY",      "region": "US", "unit": "%", "fred": "PCEPILFE",         "transform": "yoy_pct"},
            {"id": "uk_cpi_yoy",   "name": "UK CPI YoY",           "region": "UK", "unit": "%", "ons": "D7G7", "ons_dataset": "mm23", "ons_path": "economy/inflationandpriceindices", "fred": "GBRCPIALLMINMEI", "transform": "yoy_pct", "note": "ONS CPI 12-month rate (published ~6w lag). FRED-OECD fallback ~3m further behind."},
            {"id": "eu_cpi_yoy",   "name": "Eurozone CPI YoY",     "region": "EU", "unit": "%", "fred": "CP0000EZ19M086NEST","transform": "yoy_pct"},
            {"id": "jp_cpi_yoy",   "name": "Japan CPI YoY",        "region": "JP", "unit": "%", "fred": "JPNCPIALLMINMEI",  "transform": "yoy_pct"},
            {"id": "de_cpi_yoy",   "name": "Germany CPI YoY",      "region": "DE", "unit": "%", "fred": "DEUCPIALLMINMEI",  "transform": "yoy_pct"},
            {"id": "fr_cpi_yoy",   "name": "France CPI YoY",       "region": "FR", "unit": "%", "fred": "FRACPIALLMINMEI",  "transform": "yoy_pct"},
            {"id": "ca_cpi_yoy",   "name": "Canada CPI YoY",       "region": "CA", "unit": "%", "fred": "CANCPIALLMINMEI",  "transform": "yoy_pct"},
            {"id": "au_cpi_yoy",   "name": "Australia CPI YoY",    "region": "AU", "unit": "%", "fred": "AUSCPIALLQINMEI",  "transform": "yoy_pct", "freq": "q"},
            {"id": "us_ppi_yoy",   "name": "US Producer Prices YoY","region": "US", "unit": "%", "fred": "PPIACO",          "transform": "yoy_pct"},
        ],
    },

    # ───────────────────────────── MONEY SUPPLY ─────────────────────────────
    "money": {
        "title": "Money & Liquidity",
        "icon": "savings",
        "blurb": "How much money is sloshing around the system.",
        "series": [
            {"id": "us_m2",       "name": "US M2 Money Supply",   "region": "US", "unit": "$bn", "fred": "M2SL"},
            {"id": "us_m2_yoy",   "name": "US M2 Growth YoY",     "region": "US", "unit": "%",   "fred": "M2SL",         "transform": "yoy_pct"},
            {"id": "us_m1",       "name": "US M1 Money Supply",   "region": "US", "unit": "$bn", "fred": "M1SL"},
            {"id": "us_monbase",  "name": "US Monetary Base",     "region": "US", "unit": "$bn", "fred": "BOGMBASE"},
            {"id": "uk_m4",       "name": "UK M4 Money Supply",   "region": "UK", "unit": "£m",  "fred": "MABMM301GBM189N"},
            {"id": "uk_m4_yoy",   "name": "UK M4 Growth YoY",     "region": "UK", "unit": "%",   "fred": "MABMM301GBM189N", "transform": "yoy_pct"},
            {"id": "eu_m3",       "name": "Eurozone M3",          "region": "EU", "unit": "€bn", "fred": "MYAGM3EZM196N"},
            {"id": "jp_m2",       "name": "Japan M2",             "region": "JP", "unit": "¥bn", "fred": "MYAGM2JPM189N"},
            {"id": "fed_balance", "name": "Fed Balance Sheet",    "region": "US", "unit": "$bn", "fred": "WALCL"},
            {"id": "us_credit_gdp","name": "US Private Credit/GDP","region": "US", "unit": "%",  "fred": "QUSPAMUSDA"},
        ],
    },

    # ───────────────────────────── HOUSING ─────────────────────────────
    "housing": {
        "title": "Housing",
        "icon": "home",
        "blurb": "Residential property — the household balance-sheet anchor.",
        "series": [
            {"id": "uk_avg_price", "name": "UK Average House Price",      "region": "UK",   "unit": "£",     "uk_hpi": "United Kingdom",         "note": "HM Land Registry monthly mean price (£)."},
            {"id": "uk_eng_price", "name": "England Average House Price", "region": "UK",   "unit": "£",     "uk_hpi": "England"},
            {"id": "uk_wal_price", "name": "Wales Average House Price",   "region": "UK",   "unit": "£",     "uk_hpi": "Wales"},
            {"id": "uk_sco_price", "name": "Scotland Average House Price","region": "UK",   "unit": "£",     "uk_hpi": "Scotland"},
            {"id": "uk_ni_price",  "name": "N.Ireland Avg House Price",   "region": "UK",   "unit": "£",     "uk_hpi": "Northern Ireland"},
            {"id": "uk_lon_price", "name": "London Average House Price",  "region": "UK",   "unit": "£",     "uk_hpi": "London"},
            {"id": "uk_se_price",  "name": "South East House Price",      "region": "UK",   "unit": "£",     "uk_hpi": "South East"},
            {"id": "uk_sw_price",  "name": "South West House Price",      "region": "UK",   "unit": "£",     "uk_hpi": "South West"},
            {"id": "uk_em_price",  "name": "East Midlands House Price",   "region": "UK",   "unit": "£",     "uk_hpi": "East Midlands"},
            {"id": "uk_wm_price",  "name": "West Midlands House Price",   "region": "UK",   "unit": "£",     "uk_hpi": "West Midlands"},
            {"id": "uk_nw_price",  "name": "North West House Price",      "region": "UK",   "unit": "£",     "uk_hpi": "North West"},
            {"id": "uk_ne_price",  "name": "North East House Price",      "region": "UK",   "unit": "£",     "uk_hpi": "North East"},
            {"id": "uk_yh_price",  "name": "Yorkshire & Humber Price",    "region": "UK",   "unit": "£",     "uk_hpi": "Yorkshire and The Humber"},
            {"id": "uk_ee_price",  "name": "East of England Price",       "region": "UK",   "unit": "£",     "uk_hpi": "East of England"},
            {"id": "uk_hpi",       "name": "UK House Price Index (BIS)",  "region": "UK",   "unit": "index", "fred": "QGBN628BIS",  "freq": "q", "note": "BIS, 2010=100. Long-history index."},
            {"id": "us_caseshiller","name": "US Case-Shiller HPI", "region": "US", "unit": "index", "fred": "CSUSHPISA",                "note": "20-city composite."},
            {"id": "us_fhfa",      "name": "US FHFA HPI",          "region": "US", "unit": "index", "fred": "USSTHPI",     "freq": "q"},
            {"id": "us_starts",    "name": "US Housing Starts",    "region": "US", "unit": "k",     "fred": "HOUST",                     "note": "New residential construction."},
            {"id": "uk_starts",    "name": "UK Dwelling Starts",   "region": "UK", "unit": "units", "fred": "ODCNPI03GBQ661N", "freq":"q"},
            {"id": "au_hpi",       "name": "Australia HPI",        "region": "AU", "unit": "index", "fred": "QAUN628BIS",  "freq": "q"},
            {"id": "jp_hpi",       "name": "Japan HPI",            "region": "JP", "unit": "index", "fred": "QJPN628BIS",  "freq": "q"},
            {"id": "ca_hpi",       "name": "Canada HPI",           "region": "CA", "unit": "index", "fred": "QCAN628BIS",  "freq": "q"},
            {"id": "cn_hpi",       "name": "China HPI",            "region": "CN", "unit": "index", "fred": "QCNN628BIS",  "freq": "q"},
            {"id": "de_hpi",       "name": "Germany HPI",          "region": "DE", "unit": "index", "fred": "QDER628BIS",  "freq": "q"},
            {"id": "fr_hpi",       "name": "France HPI",           "region": "FR", "unit": "index", "fred": "QFRN628BIS",  "freq": "q"},
            {"id": "us_mortgage_30y","name": "US 30Y Mortgage",    "region": "US", "unit": "%",     "fred": "MORTGAGE30US"},
            {"id": "us_delinq",    "name": "US Mortgage Delinquency","region": "US","unit": "%",   "fred": "DRSFRMACBS",  "freq": "q"},
        ],
    },

    # ───────────────────────────── COMMODITIES ─────────────────────────────
    "commodities": {
        "title": "Commodities",
        "icon": "oil_barrel",
        "blurb": "Raw materials — the real-economy temperature gauge.",
        "series": [
            {"id": "oil_wti",   "name": "Crude Oil (WTI)",     "region": "GLOBAL", "unit": "$/bbl", "yahoo": "CL=F", "fred": "DCOILWTICO"},
            {"id": "oil_brent", "name": "Crude Oil (Brent)",   "region": "GLOBAL", "unit": "$/bbl", "yahoo": "BZ=F", "fred": "DCOILBRENTEU"},
            {"id": "gold",      "name": "Gold",                "region": "GLOBAL", "unit": "$/oz",  "yahoo": "GC=F", "fred": "GOLDAMGBD228NLBM"},
            {"id": "silver",    "name": "Silver",              "region": "GLOBAL", "unit": "$/oz",  "yahoo": "SI=F"},
            {"id": "platinum",  "name": "Platinum",            "region": "GLOBAL", "unit": "$/oz",  "yahoo": "PL=F"},
            {"id": "natgas",    "name": "Natural Gas",         "region": "US",     "unit": "$/MMBtu","yahoo": "NG=F", "fred": "DHHNGSP"},
            {"id": "copper",    "name": "Copper",              "region": "GLOBAL", "unit": "$/lb",  "yahoo": "HG=F"},
            {"id": "wheat",     "name": "Wheat",               "region": "GLOBAL", "unit": "¢/bu",  "yahoo": "ZW=F"},
            {"id": "corn",      "name": "Corn",                "region": "GLOBAL", "unit": "¢/bu",  "yahoo": "ZC=F"},
            {"id": "coffee",    "name": "Coffee",              "region": "GLOBAL", "unit": "¢/lb",  "yahoo": "KC=F"},
            {"id": "sugar",     "name": "Sugar",               "region": "GLOBAL", "unit": "¢/lb",  "yahoo": "SB=F"},
            {"id": "uranium",   "name": "Uranium",             "region": "GLOBAL", "unit": "$/lb",  "yahoo": "UX=F"},
            {"id": "us_gas_pump","name": "US Retail Gasoline", "region": "US",     "unit": "$/gal", "fred": "GASREGW"},
            {"id": "us_diesel_pump","name": "US Retail Diesel","region": "US",     "unit": "$/gal", "fred": "GASDESW"},
            {"id": "uk_petrol", "name": "UK Pump Petrol (ULSP)","region": "UK",    "unit": "p/L",   "uk_fuel": "petrol", "note": "DESNZ weekly road fuel survey."},
            {"id": "uk_diesel", "name": "UK Pump Diesel (ULSD)","region": "UK",    "unit": "p/L",   "uk_fuel": "diesel", "note": "DESNZ weekly road fuel survey."},
        ],
    },

    # ───────────────────────────── CURRENCIES ─────────────────────────────
    "fx": {
        "title": "Currencies",
        "icon": "currency_exchange",
        "blurb": "Exchange rates and the dollar's grip on global liquidity.",
        "series": [
            {"id": "gbp_usd",  "name": "GBP/USD",   "region": "FX", "unit": "rate", "yahoo": "GBPUSD=X", "fred": "DEXUSUK"},
            {"id": "eur_usd",  "name": "EUR/USD",   "region": "FX", "unit": "rate", "yahoo": "EURUSD=X", "fred": "DEXUSEU"},
            {"id": "usd_jpy",  "name": "USD/JPY",   "region": "FX", "unit": "rate", "yahoo": "JPY=X",    "fred": "DEXJPUS"},
            {"id": "usd_cny",  "name": "USD/CNY",   "region": "FX", "unit": "rate", "yahoo": "CNY=X",    "fred": "DEXCHUS"},
            {"id": "usd_chf",  "name": "USD/CHF",   "region": "FX", "unit": "rate", "yahoo": "CHF=X",    "fred": "DEXSZUS"},
            {"id": "aud_usd",  "name": "AUD/USD",   "region": "FX", "unit": "rate", "yahoo": "AUDUSD=X", "fred": "DEXUSAL"},
            {"id": "usd_cad",  "name": "USD/CAD",   "region": "FX", "unit": "rate", "yahoo": "CAD=X",    "fred": "DEXCAUS"},
            {"id": "usd_inr",  "name": "USD/INR",   "region": "FX", "unit": "rate", "yahoo": "INR=X",    "fred": "DEXINUS"},
            {"id": "usd_brl",  "name": "USD/BRL",   "region": "FX", "unit": "rate", "yahoo": "BRL=X",    "fred": "DEXBZUS"},
            {"id": "usd_mxn",  "name": "USD/MXN",   "region": "FX", "unit": "rate", "yahoo": "MXN=X",    "fred": "DEXMXUS"},
            {"id": "dxy",      "name": "DXY Dollar Index", "region": "US", "unit": "index", "yahoo": "DX-Y.NYB", "fred": "DTWEXBGS"},
            {"id": "btc_usd",  "name": "Bitcoin",   "region": "GLOBAL", "unit": "USD", "yahoo": "BTC-USD"},
            {"id": "eth_usd",  "name": "Ethereum",  "region": "GLOBAL", "unit": "USD", "yahoo": "ETH-USD"},
        ],
    },

    # ───────────────────────────── EMPLOYMENT ─────────────────────────────
    "employment": {
        "title": "Employment",
        "icon": "groups",
        "blurb": "Jobs, unemployment, participation, age & gender splits.",
        "series": [
            # ── UK headline + age bands + gender splits (the granularity the user asked for) ──
            {"id": "uk_unrate",         "name": "UK Unemployment Rate",       "region": "UK", "unit": "%", "ons": "MGSX", "ons_dataset": "lms", "ons_path": "employmentandlabourmarket/peoplenotinwork/unemployment", "fred": "LRHUTTTTGBM156S", "note": "ONS direct (16+, SA) — published with ~6-week lag. FRED-OECD fallback runs ~3 months further behind."},
            {"id": "uk_unrate_youth",   "name": "UK Youth (15-24)",           "region": "UK", "unit": "%", "fred": "LRHU24TTGBM156S",                 "note": "OECD UK unemployment rate ages 15-24, monthly."},
            {"id": "uk_unrate_core",    "name": "UK Core-Age (25-54)",        "region": "UK", "unit": "%", "fred": "LRUN25TTGBQ156S", "freq": "q",    "note": "OECD UK unemployment rate ages 25-54, quarterly."},
            {"id": "uk_unrate_senior",  "name": "UK Senior (55-64)",          "region": "UK", "unit": "%", "fred": "LRUN55TTGBQ156S", "freq": "q",    "note": "OECD UK unemployment rate ages 55-64, quarterly."},
            {"id": "uk_unrate_male",    "name": "UK Male Unemployment",       "region": "UK", "unit": "%", "fred": "LRHUTTMAGBM156S",                 "note": "OECD UK male 15+ unemployment, monthly."},
            {"id": "uk_unrate_female",  "name": "UK Female Unemployment",     "region": "UK", "unit": "%", "fred": "LRHUTTFEGBM156S",                 "note": "OECD UK female 15+ unemployment, monthly."},
            # ── US headline + age bands ──
            {"id": "us_unrate",         "name": "US Unemployment Rate",       "region": "US", "unit": "%", "fred": "UNRATE",                          "note": "BLS US headline U-3 rate, monthly."},
            {"id": "us_unrate_16_19",   "name": "US Teen (16-19)",            "region": "US", "unit": "%", "fred": "LNS14000012",                     "note": "BLS US unemployment rate ages 16-19, monthly."},
            {"id": "us_unrate_20_24",   "name": "US Young Adult (20-24)",     "region": "US", "unit": "%", "fred": "LNS14000036"},
            {"id": "us_unrate_25_34",   "name": "US Adult (25-34)",           "region": "US", "unit": "%", "fred": "LNU04000089",                     "note": "BLS US 25-34, monthly NSA."},
            {"id": "us_unrate_55plus",  "name": "US 55+",                     "region": "US", "unit": "%", "fred": "LNS14024230"},
            {"id": "us_unrate_youth",   "name": "US Youth Aggregate (16-24)", "region": "US", "unit": "%", "fred": "LNS14024887"},
            {"id": "us_long_term",      "name": "US Long-Term Unemployed (15+ wk)","region":"US","unit":"k","fred":"UEMP15OV",                       "note": "BLS count of people unemployed 15 weeks or longer."},
            # ── Other countries (headline only) ──
            {"id": "eu_unrate",         "name": "Eurozone Unemployment",      "region": "EU", "unit": "%", "fred": "LRHUTTTTEZM156S"},
            {"id": "de_unrate",         "name": "Germany Unemployment",       "region": "DE", "unit": "%", "fred": "LRHUTTTTDEM156S"},
            {"id": "fr_unrate",         "name": "France Unemployment",        "region": "FR", "unit": "%", "fred": "LRHUTTTTFRM156S"},
            {"id": "jp_unrate",         "name": "Japan Unemployment",         "region": "JP", "unit": "%", "fred": "LRHUTTTTJPM156S"},
            {"id": "ca_unrate",         "name": "Canada Unemployment",        "region": "CA", "unit": "%", "fred": "LRHUTTTTCAM156S"},
            {"id": "au_unrate",         "name": "Australia Unemployment",     "region": "AU", "unit": "%", "fred": "LRHUTTTTAUM156S"},
            {"id": "cn_unrate",         "name": "China Youth Unemployment",   "region": "CN", "unit": "%", "fred": "SLUEM1524ZSCHN",                  "note": "World Bank annual data."},
            # ── US flow / participation ──
            {"id": "us_payrolls",       "name": "US Nonfarm Payrolls",        "region": "US", "unit": "k", "fred": "PAYEMS"},
            {"id": "us_partrate",       "name": "US Labor Participation",     "region": "US", "unit": "%", "fred": "CIVPART"},
            {"id": "us_claims",         "name": "US Initial Jobless Claims",  "region": "US", "unit": "k", "fred": "ICSA", "freq": "w"},
        ],
    },

    # ───────────────────────────── MACRO OUTPUT ─────────────────────────────
    "macro": {
        "title": "Growth & Output",
        "icon": "factory",
        "blurb": "GDP, industrial production, sentiment, leading indicators.",
        "series": [
            {"id": "us_gdp",       "name": "US Real GDP",         "region": "US", "unit": "$bn", "fred": "GDPC1",   "freq": "q"},
            {"id": "us_gdp_yoy",   "name": "US GDP Growth YoY",   "region": "US", "unit": "%",   "fred": "GDPC1",   "freq": "q", "transform": "yoy_pct"},
            {"id": "uk_gdp",       "name": "UK Real GDP",         "region": "UK", "unit": "£bn", "fred": "NGDPRSAXDCGBQ", "freq": "q"},
            {"id": "uk_gdp_yoy",   "name": "UK GDP Growth YoY",   "region": "UK", "unit": "%",   "fred": "NGDPRSAXDCGBQ", "freq": "q", "transform": "yoy_pct"},
            {"id": "de_gdp",       "name": "Germany Real GDP",    "region": "DE", "unit": "€bn", "fred": "CLVMNACSCAB1GQDE", "freq": "q"},
            {"id": "jp_gdp",       "name": "Japan Real GDP",      "region": "JP", "unit": "¥bn", "fred": "JPNRGDPEXP","freq": "q"},
            {"id": "us_indprod",   "name": "US Industrial Production","region":"US","unit":"index","fred":"INDPRO"},
            {"id": "us_retail",    "name": "US Retail Sales",     "region": "US", "unit": "$m", "fred": "RSXFS"},
            {"id": "uk_retail",    "name": "UK Retail Sales",     "region": "UK", "unit": "index","fred": "GBRSLRTTO02IXOBSAM"},
            {"id": "us_leading",   "name": "US Leading Index",    "region": "US", "unit": "%",  "fred": "USSLIND"},
            {"id": "us_sentiment", "name": "US Consumer Sentiment","region":"US", "unit": "index","fred": "UMCSENT"},
            {"id": "us_recession", "name": "US Recession Indicator","region":"US","unit": "0/1", "fred": "USREC"},
        ],
    },

    # ───────────────────────────── RISK / STRESS ─────────────────────────────
    "risk": {
        "title": "Risk & Stress",
        "icon": "warning",
        "blurb": "Volatility, credit spreads, financial stress indicators.",
        "series": [
            {"id": "vix",          "name": "VIX (Fear Index)",      "region": "US", "unit": "vol", "fred": "VIXCLS"},
            {"id": "stl_fsi",      "name": "St. Louis Fed Stress",  "region": "US", "unit": "index","fred": "STLFSI4", "freq": "w"},
            {"id": "hy_oas",       "name": "US High-Yield OAS",     "region": "US", "unit": "%",   "fred": "BAMLH0A0HYM2"},
            {"id": "ig_oas",       "name": "US Investment-Grade OAS","region":"US","unit": "%",   "fred": "BAMLC0A0CM"},
            {"id": "ted",          "name": "US AA Financial Spread","region": "US", "unit": "bps","fred": "BAMLC0A2CAA"},
            {"id": "us_delinq_cc", "name": "US Credit-Card Delinquency","region":"US","unit":"%", "fred": "DRCCLACBS", "freq": "q"},
            {"id": "us_ccc_oas",   "name": "US CCC Junk Spread",    "region": "US", "unit": "%",   "fred": "BAMLH0A3HYC"},
            {"id": "move_index",   "name": "MOVE Bond Vol Index",   "region": "US", "unit": "index","yahoo":"^MOVE", "note":"Treasury volatility — the 'VIX of bonds'."},
            {"id": "us_finstr",    "name": "Chicago Fed NFCI",      "region": "US", "unit": "index","fred":"NFCI", "freq":"w", "note":"Composite of 100+ financial stress indicators."},
        ],
    },
}


# Major hand-curated economic events for the timeline.
# Edit this list to add or revise events.
EVENTS = [
    {"date": "1971-08-15", "title": "Nixon Shock — End of Gold Standard", "tag": "monetary",  "impact": "high", "blurb": "US suspends dollar convertibility into gold, ending Bretton Woods and ushering in the fiat era."},
    {"date": "1973-10-17", "title": "OPEC Oil Embargo",                  "tag": "oil",       "impact": "high", "blurb": "Arab members of OPEC declare embargo; oil prices quadruple within months."},
    {"date": "1979-10-06", "title": "Volcker Shock Begins",               "tag": "monetary",  "impact": "high", "blurb": "Fed Chair Paul Volcker hikes rates aggressively to crush double-digit inflation."},
    {"date": "1979-11-04", "title": "Iranian Revolution / Second Oil Shock","tag": "oil",     "impact": "high", "blurb": "Iran's revolution disrupts oil supply; prices double again."},
    {"date": "1981-08-13", "title": "Reagan Tax Cuts (ERTA)",             "tag": "fiscal",    "impact": "med",  "blurb": "Economic Recovery Tax Act — large supply-side US tax cuts."},
    {"date": "1985-09-22", "title": "Plaza Accord",                       "tag": "fx",        "impact": "high", "blurb": "G5 nations coordinate to weaken the US dollar."},
    {"date": "1987-10-19", "title": "Black Monday",                       "tag": "markets",   "impact": "high", "blurb": "Global stock crash; Dow falls 22.6% in one day."},
    {"date": "1989-11-09", "title": "Fall of the Berlin Wall",            "tag": "geopolitical","impact":"med", "blurb": "Beginning of German reunification and the end of the Cold War economic divide."},
    {"date": "1990-08-02", "title": "Gulf War / Oil Spike",               "tag": "oil",       "impact": "med",  "blurb": "Iraq invades Kuwait; oil briefly doubles."},
    {"date": "1992-09-16", "title": "Black Wednesday",                    "tag": "fx",        "impact": "high", "blurb": "UK forced out of ERM; sterling collapses, Soros profits ~$1bn."},
    {"date": "1994-12-20", "title": "Mexican Peso Crisis",                "tag": "crisis",    "impact": "med",  "blurb": "Tequila crisis — emerging-market contagion."},
    {"date": "1997-07-02", "title": "Asian Financial Crisis",             "tag": "crisis",    "impact": "high", "blurb": "Thai baht collapse triggers regional currency rout."},
    {"date": "1998-08-17", "title": "Russian Default & LTCM Collapse",    "tag": "crisis",    "impact": "high", "blurb": "Russia defaults; hedge fund LTCM nearly takes down global banks."},
    {"date": "1999-01-01", "title": "Euro Launched",                      "tag": "monetary",  "impact": "high", "blurb": "Single European currency goes live (notes & coins in 2002)."},
    {"date": "2000-03-10", "title": "Dot-com Peak",                       "tag": "markets",   "impact": "high", "blurb": "NASDAQ peaks at 5,048 — collapses 78% over next 2.5 years."},
    {"date": "2001-09-11", "title": "9/11 Attacks",                       "tag": "geopolitical","impact":"high","blurb": "NYSE closed for 4 days; insurance, airline, oil shocks follow."},
    {"date": "2002-01-01", "title": "Euro Notes & Coins",                 "tag": "monetary",  "impact": "low",  "blurb": "Physical euro replaces 12 national currencies."},
    {"date": "2007-08-09", "title": "Subprime Crisis Begins",             "tag": "crisis",    "impact": "high", "blurb": "BNP Paribas freezes funds; credit markets seize."},
    {"date": "2008-09-15", "title": "Lehman Brothers Collapses",          "tag": "crisis",    "impact": "high", "blurb": "Largest bankruptcy in US history; Global Financial Crisis erupts."},
    {"date": "2008-11-25", "title": "Fed Launches QE1",                   "tag": "monetary",  "impact": "high", "blurb": "Fed begins large-scale asset purchases."},
    {"date": "2009-03-09", "title": "Bull Market Bottom",                 "tag": "markets",   "impact": "high", "blurb": "S&P 500 bottoms at 666; longest bull market in history begins."},
    {"date": "2010-05-02", "title": "Greek Bailout #1",                   "tag": "crisis",    "impact": "med",  "blurb": "European sovereign-debt crisis begins."},
    {"date": "2011-08-05", "title": "S&P Downgrades US",                  "tag": "credit",    "impact": "med",  "blurb": "First-ever downgrade of US sovereign rating."},
    {"date": "2012-07-26", "title": "Draghi 'Whatever It Takes'",         "tag": "monetary",  "impact": "high", "blurb": "ECB pledges to save the euro; bond yields collapse."},
    {"date": "2014-06-05", "title": "ECB Goes Negative",                  "tag": "monetary",  "impact": "high", "blurb": "ECB deposit rate cut to -0.10% — first major NIRP."},
    {"date": "2014-11-01", "title": "Oil Collapse Begins",                "tag": "oil",       "impact": "high", "blurb": "Brent falls from $115 to $26 by Jan 2016."},
    {"date": "2015-06-12", "title": "Chinese Stock Crash",                "tag": "markets",   "impact": "med",  "blurb": "Shanghai Composite loses 30% in 3 weeks."},
    {"date": "2016-06-23", "title": "Brexit Referendum",                  "tag": "geopolitical","impact":"high", "blurb": "UK votes 52-48 to leave EU; GBP falls 8% overnight."},
    {"date": "2018-02-05", "title": "Volmageddon",                        "tag": "markets",   "impact": "med",  "blurb": "Short-vol funds blow up; VIX doubles in a day."},
    {"date": "2018-12-24", "title": "Q4 2018 Selloff",                    "tag": "markets",   "impact": "med",  "blurb": "S&P falls ~20% peak-to-trough on Fed-tightening fears."},
    {"date": "2020-03-09", "title": "Oil Price War + COVID Crash",        "tag": "crisis",    "impact": "high", "blurb": "Saudi-Russia oil war collides with pandemic; circuit breakers tripped."},
    {"date": "2020-03-23", "title": "Fed Unlimited QE",                   "tag": "monetary",  "impact": "high", "blurb": "Fed announces uncapped asset purchases; market bottom."},
    {"date": "2020-04-20", "title": "Oil Goes Negative",                  "tag": "oil",       "impact": "high", "blurb": "WTI May futures settle at -$37.63 — first ever negative print."},
    {"date": "2021-01-27", "title": "GameStop Short Squeeze",             "tag": "markets",   "impact": "low",  "blurb": "Retail traders squeeze hedge-fund shorts; meme-stock era."},
    {"date": "2022-02-24", "title": "Russia Invades Ukraine",             "tag": "geopolitical","impact":"high", "blurb": "Energy & food prices spike; sanctions and SWIFT cutoffs."},
    {"date": "2022-03-17", "title": "Fed Tightening Begins",              "tag": "monetary",  "impact": "high", "blurb": "Fastest hiking cycle in 40 years to combat 9% inflation."},
    {"date": "2022-09-23", "title": "UK Mini-Budget Crisis",              "tag": "fiscal",    "impact": "high", "blurb": "Truss/Kwarteng tax cuts trigger gilt crash; BoE emergency intervention."},
    {"date": "2023-03-10", "title": "SVB & Banking Stress",               "tag": "crisis",    "impact": "high", "blurb": "Silicon Valley Bank fails; Credit Suisse rescued by UBS."},
    {"date": "2023-10-07", "title": "Israel-Hamas War",                   "tag": "geopolitical","impact":"med", "blurb": "Middle East tensions reset oil-risk premium."},
    {"date": "2024-08-05", "title": "Yen Carry Trade Unwind",             "tag": "fx",        "impact": "high", "blurb": "BoJ hike triggers global vol spike; Nikkei -12% in a day."},
    {"date": "2024-11-05", "title": "Trump Wins US Election",             "tag": "geopolitical","impact":"high","blurb": "Republican sweep; tariff and tax-cut agenda priced into markets."},
    {"date": "2025-04-02", "title": "Liberation Day Tariffs",             "tag": "trade",     "impact": "high", "blurb": "Sweeping reciprocal US tariffs announced; global market rout."},
]
