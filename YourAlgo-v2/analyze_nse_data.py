import os
import glob
import pandas as pd
import json

nse_dir = r"c:\Users\patel\Desktop\Algo Trading\NSE data"

# 1. Inspect EQUITY_L.csv
eq_path = os.path.join(nse_dir, "EQUITY_L.csv")
if os.path.exists(eq_path):
    df_eq = pd.read_csv(eq_path)
    df_eq.columns = [c.strip() for c in df_eq.columns]
    print(f"EQUITY_L count: {len(df_eq)}")
    print("Columns:", list(df_eq.columns))
    print("Sample:\n", df_eq.head(2).to_dict(orient="records"))

# 2. Inspect eq_etfseclist.csv
etf_path = os.path.join(nse_dir, "eq_etfseclist.csv")
if os.path.exists(etf_path):
    df_etf = pd.read_csv(etf_path)
    df_etf.columns = [c.strip() for c in df_etf.columns]
    print(f"\nETF count: {len(df_etf)}")
    print("Columns:", list(df_etf.columns))
    print("Sample:\n", df_etf.head(2).to_dict(orient="records"))

# 3. Inspect SME_EQUITY_L.csv
sme_path = os.path.join(nse_dir, "SME_EQUITY_L.csv")
if os.path.exists(sme_path):
    df_sme = pd.read_csv(sme_path)
    df_sme.columns = [c.strip() for c in df_sme.columns]
    print(f"\nSME count: {len(df_sme)}")
    print("Sample:\n", df_sme.head(2).to_dict(orient="records"))

# 4. Inspect CDC_Record_Date_Details_0.csv
cdc_path = os.path.join(nse_dir, "CDC_Record_Date_Details_0.csv")
if os.path.exists(cdc_path):
    try:
        df_cdc = pd.read_csv(cdc_path, nrows=50)
        df_cdc.columns = [c.strip() for c in df_cdc.columns]
        print(f"\nCDC Record Date columns:", list(df_cdc.columns))
        print("Sample Purpose values:", df_cdc['Purpose'].value_counts().to_dict())
    except Exception as e:
        print("CDC error:", e)

# 5. Inspect Credit_Rating_Details.csv (read sample)
cr_path = os.path.join(nse_dir, "Credit_Rating_Details.csv")
if os.path.exists(cr_path):
    try:
        df_cr = pd.read_csv(cr_path, nrows=50)
        df_cr.columns = [c.strip() for c in df_cr.columns]
        print(f"\nCredit Rating columns:", list(df_cr.columns))
        print("Sample Rating Agencies:", df_cr['Name of Credit Rating Agency'].value_counts().to_dict())
    except Exception as e:
        print("Credit Rating error:", e)
