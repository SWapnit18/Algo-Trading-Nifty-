"""
====================================================================
NSE Data to MySQL Warehouse Ingestion Pipeline
National Stock Exchange of India (NSE) Datasets
====================================================================
Ingests official NSE CSV files into MySQL 8.0 with normalized tables,
indexes, and chunked batch insertion.
"""

import os
import sys
import argparse
import time
import math
import pandas as pd
import pymysql
from typing import Dict, Any, List

# Reconfigure stdout/stderr for Windows PowerShell UTF-8 support
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_NSE_DIR = r"c:\Users\patel\Desktop\Algo Trading\NSE data"

# Heuristic sector mapping for equities
SECTOR_KEYWORDS = {
    "Banking & Finance": [
        "BANK", "FINANCE", "CAPITAL", "HOUSING", "INVEST", "FINSERV", "CREDIT",
        "HOLDINGS", "SECURITIES", "MUTUAL", "ASSET", "INSURANCE", "CHOLA", "BAJAJ"
    ],
    "Information Technology": [
        "TECH", "INFOSYS", "TCS", "WIPRO", "HCL", "SOFTWARE", "SYSTEMS", "DIGITAL",
        "CYBER", "INFOTECH", "SOLUTIONS", "DATA", "MINDTREE", "LTIM", "COFORGE", "PERSISTENT"
    ],
    "Automobile & Auto Ancillary": [
        "MOTORS", "AUTO", "TYRES", "FORGINGS", "MARUTI", "HERO", "BAJAJ-AUTO", "EICHER",
        "MAHINDRA", "TUBE", "EXIDE", "AMARA", "BHARATFORG", "SONA", "BOSCH"
    ],
    "Energy & Utilities": [
        "POWER", "ENERGY", "OIL", "GAS", "PETRO", "NTPC", "RELIANCE", "ADANI", "COAL",
        "IOC", "BPCL", "HPCL", "ONGC", "GAIL", "SOLAR", "GRID", "TATA POWER"
    ],
    "Pharmaceuticals & Healthcare": [
        "PHARMA", "LABS", "HEALTH", "DRUG", "HOSPITAL", "LIFE", "MED", "BIOCON",
        "SUNPHARMA", "CIPLA", "REDDY", "DIVIS", "LUPIN", "APOLLO", "FORTIS", "MANKIND"
    ],
    "Consumer Goods & FMCG": [
        "FOOD", "BEVERAGE", "CONSUMER", "SUGAR", "BREW", "TOBACCO", "NESTLE", "HINDUNILVR",
        "BRITANNIA", "DABUR", "MARICO", "GODREJ", "ITC", "TATA CONSUMER", "VARUN"
    ],
    "Metals & Mining": [
        "STEEL", "METAL", "MINING", "ALUMINIUM", "COPPER", "ZINC", "TATASTEEL", "JSWSTEEL",
        "HINDALCO", "VEDL", "JINDAL", "SAIL", "NMDC", "MINERALS"
    ],
    "Infrastructure & Industrials": [
        "ENGINEERING", "INFRA", "CONSTRUCT", "CEMENT", "PROJECTS", "LT", "LARSEN",
        "ULTRACEMCO", "AMBUJA", "ACC", "DLF", "GODREJPROP", "CONTAINER", "PORT"
    ],
    "Telecommunications": [
        "TELECOM", "AIRTEL", "BHARTI", "TOWER", "COMMUNICATION", "VODAFONE", "IDEA", "TATA COMM"
    ],
    "Chemicals & Fertilizers": [
        "CHEMICAL", "FERTILIZER", "ORGANIC", "SPECIALTY", "POLYMER", "AGRO", "AARTI",
        "SRF", "PIIND", "DEEPAK", "ATUL", "UPL"
    ]
}

def determine_sector(symbol: str, company_name: str) -> str:
    sym = (symbol or "").upper()
    name = (company_name or "").upper()
    text = f"{sym} {name}"
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(k in text for k in keywords):
            return sector
    return "Diversified Industrials"

def safe_float(val, default=0.0):
    try:
        if pd.isna(val):
            return default
        clean = str(val).replace(",", "").strip()
        return float(clean)
    except Exception:
        return default

def safe_int(val, default=1):
    try:
        if pd.isna(val):
            return default
        clean = str(val).replace(",", "").strip()
        return int(float(clean))
    except Exception:
        return default

def safe_str(val, max_len=255, default=""):
    if pd.isna(val) or val is None:
        return default
    s = str(val).strip()
    if s.lower() == "nan":
        return default
    return s[:max_len]

def create_database_and_tables(conn, db_name: str):
    cur = conn.cursor()
    print(f"[*] Ensuring database `{db_name}` exists...")
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    cur.execute(f"USE `{db_name}`;")

    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS nse_equities (
            symbol VARCHAR(30) NOT NULL PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            series VARCHAR(10) DEFAULT 'EQ',
            date_of_listing VARCHAR(30),
            paid_up_value DECIMAL(14, 2) DEFAULT 0.00,
            market_lot INT DEFAULT 1,
            isin VARCHAR(30),
            face_value DECIMAL(14, 2) DEFAULT 10.00,
            sector VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_eq_isin (isin),
            INDEX idx_eq_sector (sector)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS nse_etfs (
            symbol VARCHAR(30) NOT NULL PRIMARY KEY,
            security_name VARCHAR(255) NOT NULL,
            underlying_asset VARCHAR(255),
            category VARCHAR(100) DEFAULT 'EQUITY',
            isin VARCHAR(30),
            listing_date VARCHAR(30),
            face_value DECIMAL(14, 2) DEFAULT 1.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_etf_isin (isin),
            INDEX idx_etf_category (category)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS nse_sme_equities (
            symbol VARCHAR(30) NOT NULL PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            series VARCHAR(10) DEFAULT 'SM',
            listing_date VARCHAR(30),
            paid_up_value DECIMAL(14, 2) DEFAULT 0.00,
            market_lot INT DEFAULT 1,
            isin VARCHAR(30),
            face_value DECIMAL(14, 2) DEFAULT 10.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_sme_isin (isin)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS nse_corporate_actions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            purpose TEXT NOT NULL,
            record_date VARCHAR(50),
            bc_start_date VARCHAR(50),
            bc_end_date VARCHAR(50),
            payment_date VARCHAR(50),
            isin VARCHAR(30),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_ca_isin (isin),
            INDEX idx_ca_record_date (record_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS nse_credit_ratings (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            symbol VARCHAR(30),
            company_name VARCHAR(255),
            agency VARCHAR(100),
            credit_rating VARCHAR(50),
            rating_action VARCHAR(100),
            outlook VARCHAR(50),
            reporting_date VARCHAR(50),
            date_of_rating VARCHAR(50),
            isin VARCHAR(30),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_cr_symbol (symbol),
            INDEX idx_cr_agency (agency),
            INDEX idx_cr_rating (credit_rating),
            INDEX idx_cr_isin (isin)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS nse_debt_securities (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            symbol VARCHAR(50) NOT NULL,
            company_name VARCHAR(255) NOT NULL,
            series VARCHAR(20),
            face_value DECIMAL(16, 2) DEFAULT 0.00,
            paid_up_value DECIMAL(16, 2) DEFAULT 0.00,
            market_lot INT DEFAULT 1,
            ip_rate VARCHAR(50),
            listing_date VARCHAR(30),
            redemption_date VARCHAR(30),
            redemption_amt VARCHAR(50),
            interest_payment_date VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_debt_symbol (symbol)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS nse_name_changes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            symbol VARCHAR(30) NOT NULL,
            prev_name VARCHAR(255) NOT NULL,
            new_name VARCHAR(255) NOT NULL,
            change_date VARCHAR(30),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_nc_symbol (symbol)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS nse_symbol_changes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            old_symbol VARCHAR(30) NOT NULL,
            new_symbol VARCHAR(30) NOT NULL,
            change_date VARCHAR(30),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_sc_old (old_symbol),
            INDEX idx_sc_new (new_symbol)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS nse_slb_eligible (
            id INT AUTO_INCREMENT PRIMARY KEY,
            symbol VARCHAR(30) NOT NULL,
            series VARCHAR(10) DEFAULT 'EQ',
            normal_eligibility VARCHAR(10),
            recall_eligibility VARCHAR(10),
            repay_eligibility VARCHAR(10),
            market_type VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_slb_symbol (symbol)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    ]

    for ddl in ddl_statements:
        cur.execute(ddl)
    conn.commit()
    print("[✓] All target MySQL tables and indexes ready.")

def ingest_equities(conn, data_dir: str):
    fpath = os.path.join(data_dir, "EQUITY_L.csv")
    if not os.path.exists(fpath):
        print("[-] EQUITY_L.csv not found")
        return 0
    df = pd.read_csv(fpath)
    df.columns = [c.strip() for c in df.columns]

    rows = []
    for _, r in df.iterrows():
        sym = safe_str(r.get("SYMBOL"), 30)
        if not sym:
            continue
        name = safe_str(r.get("NAME OF COMPANY"), 255)
        sector = determine_sector(sym, name)
        rows.append((
            sym,
            name,
            safe_str(r.get("SERIES"), 10, "EQ"),
            safe_str(r.get("DATE OF LISTING"), 30),
            safe_float(r.get("PAID UP VALUE")),
            safe_int(r.get("MARKET LOT"), 1),
            safe_str(r.get("ISIN NUMBER"), 30),
            safe_float(r.get("FACE VALUE"), 10.0),
            sector
        ))

    cur = conn.cursor()
    sql = """
        INSERT INTO nse_equities (symbol, company_name, series, date_of_listing, paid_up_value, market_lot, isin, face_value, sector)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE company_name=VALUES(company_name), isin=VALUES(isin), sector=VALUES(sector);
    """
    cur.executemany(sql, rows)
    conn.commit()
    print(f"[✓] Ingested {len(rows):,} records into `nse_equities`")
    return len(rows)

def ingest_etfs(conn, data_dir: str):
    fpath = os.path.join(data_dir, "eq_etfseclist.csv")
    if not os.path.exists(fpath):
        print("[-] eq_etfseclist.csv not found")
        return 0
    df = pd.read_csv(fpath)
    df.columns = [c.strip() for c in df.columns]

    rows = []
    for _, r in df.iterrows():
        sym = safe_str(r.get("Symbol"), 30)
        if not sym:
            continue
        rows.append((
            sym,
            safe_str(r.get("SecurityName"), 255),
            safe_str(r.get("Underlying Asset"), 255),
            safe_str(r.get("ETF Underlying"), 100, "EQUITY"),
            safe_str(r.get("ISINNumber"), 30),
            safe_str(r.get("DateofListing"), 30),
            safe_float(r.get("FaceValue"), 1.0)
        ))

    cur = conn.cursor()
    sql = """
        INSERT INTO nse_etfs (symbol, security_name, underlying_asset, category, isin, listing_date, face_value)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE security_name=VALUES(security_name), underlying_asset=VALUES(underlying_asset);
    """
    cur.executemany(sql, rows)
    conn.commit()
    print(f"[✓] Ingested {len(rows):,} records into `nse_etfs`")
    return len(rows)

def ingest_sme(conn, data_dir: str):
    fpath = os.path.join(data_dir, "SME_EQUITY_L.csv")
    if not os.path.exists(fpath):
        print("[-] SME_EQUITY_L.csv not found")
        return 0
    df = pd.read_csv(fpath)
    df.columns = [c.strip() for c in df.columns]

    rows = []
    for _, r in df.iterrows():
        sym = safe_str(r.get("SYMBOL"), 30)
        if not sym:
            continue
        rows.append((
            sym,
            safe_str(r.get("NAME_OF_COMPANY"), 255),
            safe_str(r.get("SERIES"), 10, "SM"),
            safe_str(r.get("DATE_OF_LISTING"), 30),
            safe_float(r.get("PAID_UP_VALUE")),
            safe_int(r.get("MARKET_LOT"), 1),
            safe_str(r.get("ISIN_NUMBER"), 30),
            safe_float(r.get("FACE_VALUE"), 10.0)
        ))

    cur = conn.cursor()
    sql = """
        INSERT INTO nse_sme_equities (symbol, company_name, series, listing_date, paid_up_value, market_lot, isin, face_value)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE company_name=VALUES(company_name), isin=VALUES(isin);
    """
    cur.executemany(sql, rows)
    conn.commit()
    print(f"[✓] Ingested {len(rows):,} records into `nse_sme_equities`")
    return len(rows)

def ingest_corporate_actions(conn, data_dir: str):
    fpath = os.path.join(data_dir, "CDC_Record_Date_Details_0.csv")
    if not os.path.exists(fpath):
        print("[-] CDC_Record_Date_Details_0.csv not found")
        return 0
    df = pd.read_csv(fpath, on_bad_lines="skip")
    df.columns = [c.strip() for c in df.columns]

    rows = []
    for _, r in df.iterrows():
        comp = safe_str(r.get("Company Name"), 255)
        purpose = safe_str(r.get("Purpose"), 1000)
        if not comp or not purpose:
            continue
        rows.append((
            comp,
            purpose,
            safe_str(r.get("Record Date"), 50),
            safe_str(r.get("BC Start Date"), 50),
            safe_str(r.get("BC End Date"), 50),
            safe_str(r.get("Actual Payment Date"), 50),
            safe_str(r.get("ISIN"), 30)
        ))

    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE nse_corporate_actions;")
    sql = """
        INSERT INTO nse_corporate_actions (company_name, purpose, record_date, bc_start_date, bc_end_date, payment_date, isin)
        VALUES (%s, %s, %s, %s, %s, %s, %s);
    """
    batch_size = 1000
    for i in range(0, len(rows), batch_size):
        cur.executemany(sql, rows[i:i + batch_size])
    conn.commit()
    print(f"[✓] Ingested {len(rows):,} records into `nse_corporate_actions`")
    return len(rows)

def ingest_credit_ratings(conn, data_dir: str, max_rows: int = 50000):
    fpath = os.path.join(data_dir, "Credit_Rating_Details.csv")
    if not os.path.exists(fpath):
        print("[-] Credit_Rating_Details.csv not found")
        return 0

    print(f"[*] Processing `Credit_Rating_Details.csv` (Limit: {max_rows:,} rows)...")
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE nse_credit_ratings;")

    sql = """
        INSERT INTO nse_credit_ratings (symbol, company_name, agency, credit_rating, rating_action, outlook, reporting_date, date_of_rating, isin)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
    """

    total_inserted = 0
    chunk_size = 5000
    for chunk in pd.read_csv(fpath, chunksize=chunk_size, on_bad_lines="skip", low_memory=False, encoding="latin1"):
        chunk.columns = [c.strip() for c in chunk.columns]
        rows = []
        for _, r in chunk.iterrows():
            comp = safe_str(r.get("Company Name"), 255)
            agency = safe_str(r.get("Name of Credit Rating Agency"), 100)
            rating = safe_str(r.get("Credit Rating"), 50)
            if not comp or not rating:
                continue
            sym = safe_str(r.get("NSE symbol"), 30)
            if sym.lower() == "notlisted":
                sym = ""
            rows.append((
                sym,
                comp,
                agency,
                rating,
                safe_str(r.get("Rating Action"), 100, "Reaffirm"),
                safe_str(r.get("OUTLOOK"), 50, "Stable"),
                safe_str(r.get("Reporting Date"), 50),
                safe_str(r.get("Date Of Credit Rating"), 50),
                safe_str(r.get("ISIN"), 30)
            ))
        if rows:
            cur.executemany(sql, rows)
            conn.commit()
            total_inserted += len(rows)

        if max_rows and total_inserted >= max_rows:
            break

    print(f"[✓] Ingested {total_inserted:,} records into `nse_credit_ratings`")
    return total_inserted

def ingest_debt(conn, data_dir: str):
    fpath = os.path.join(data_dir, "DEBT.csv")
    if not os.path.exists(fpath):
        print("[-] DEBT.csv not found")
        return 0
    df = pd.read_csv(fpath, encoding="latin1")
    df.columns = [c.strip() for c in df.columns]

    rows = []
    for _, r in df.iterrows():
        sym = safe_str(r.get("SYMBOL"), 50)
        comp = safe_str(r.get("NAME OF COMPANY"), 255)
        if not sym or not comp:
            continue
        rows.append((
            sym,
            comp,
            safe_str(r.get("SERIES"), 20),
            safe_float(r.get("FACE VALUE")),
            safe_float(r.get("PAID UP VALUE")),
            safe_int(r.get("MKT LOT"), 1),
            safe_str(r.get("IP RATE"), 50),
            safe_str(r.get("DATE OF LISTING"), 30),
            safe_str(r.get("REDEMPTION DATE"), 30),
            safe_str(r.get("REDEMPTION AMT"), 50),
            safe_str(r.get("INTEREST PAYMENT DT"), 50)
        ))

    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE nse_debt_securities;")
    sql = """
        INSERT INTO nse_debt_securities (symbol, company_name, series, face_value, paid_up_value, market_lot, ip_rate, listing_date, redemption_date, redemption_amt, interest_payment_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """
    cur.executemany(sql, rows)
    conn.commit()
    print(f"[✓] Ingested {len(rows):,} records into `nse_debt_securities`")
    return len(rows)

def ingest_name_changes(conn, data_dir: str):
    fpath = os.path.join(data_dir, "namechange.csv")
    if not os.path.exists(fpath):
        print("[-] namechange.csv not found")
        return 0
    df = pd.read_csv(fpath, encoding="latin1")
    df.columns = [c.strip() for c in df.columns]

    rows = []
    for _, r in df.iterrows():
        sym = safe_str(r.get("NCH_SYMBOL"), 30)
        prev = safe_str(r.get("NCH_PREV_NAME"), 255)
        new_n = safe_str(r.get("NCH_NEW_NAME"), 255)
        dt = safe_str(r.get("NCH_DT"), 30)
        if sym and new_n:
            rows.append((sym, prev, new_n, dt))

    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE nse_name_changes;")
    sql = "INSERT INTO nse_name_changes (symbol, prev_name, new_name, change_date) VALUES (%s, %s, %s, %s);"
    cur.executemany(sql, rows)
    conn.commit()
    print(f"[✓] Ingested {len(rows):,} records into `nse_name_changes`")
    return len(rows)

def ingest_symbol_changes(conn, data_dir: str):
    fpath = os.path.join(data_dir, "symbolchange.csv")
    if not os.path.exists(fpath):
        print("[-] symbolchange.csv not found")
        return 0
    df = pd.read_csv(fpath, header=None, encoding="latin1")

    rows = []
    for _, r in df.iterrows():
        if len(r) >= 4:
            comp = safe_str(r[0], 255)
            old_s = safe_str(r[1], 30)
            new_s = safe_str(r[2], 30)
            dt = safe_str(r[3], 30)
            if old_s and new_s:
                rows.append((comp, old_s, new_s, dt))

    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE nse_symbol_changes;")
    sql = "INSERT INTO nse_symbol_changes (company_name, old_symbol, new_symbol, change_date) VALUES (%s, %s, %s, %s);"
    cur.executemany(sql, rows)
    conn.commit()
    print(f"[✓] Ingested {len(rows):,} records into `nse_symbol_changes`")
    return len(rows)

def ingest_slb(conn, data_dir: str):
    fpath = os.path.join(data_dir, "slb_elg_sec.csv")
    if not os.path.exists(fpath):
        print("[-] slb_elg_sec.csv not found")
        return 0
    df = pd.read_csv(fpath, encoding="latin1")
    df.columns = [c.strip() for c in df.columns]

    rows = []
    for _, r in df.iterrows():
        sym = safe_str(r.get("Symbol"), 30)
        if not sym:
            continue
        rows.append((
            sym,
            safe_str(r.get("Series"), 10, "EQ"),
            safe_str(r.get("Normal Eligibility"), 10, "Y"),
            safe_str(r.get("Recall Eligibility"), 10, "Y"),
            safe_str(r.get("Repay Eligibility"), 10, "Y"),
            safe_str(r.get("Market Type"), 20, "Normal")
        ))

    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE nse_slb_eligible;")
    sql = """
        INSERT INTO nse_slb_eligible (symbol, series, normal_eligibility, recall_eligibility, repay_eligibility, market_type)
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    cur.executemany(sql, rows)
    conn.commit()
    print(f"[✓] Ingested {len(rows):,} records into `nse_slb_eligible`")
    return len(rows)

def print_summary_report(conn, db_name: str):
    cur = conn.cursor()
    cur.execute(f"USE `{db_name}`;")
    tables = [
        "nse_equities",
        "nse_etfs",
        "nse_sme_equities",
        "nse_corporate_actions",
        "nse_credit_ratings",
        "nse_debt_securities",
        "nse_name_changes",
        "nse_symbol_changes",
        "nse_slb_eligible"
    ]
    print("\n" + "=" * 55)
    print(f"   NSE DATA WAREHOUSE MIGRATION REPORT ({db_name})")
    print("=" * 55)
    total = 0
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM `{t}`;")
            count = cur.fetchone()[0]
            print(f"  • {t:<26} : {count:>8,} rows")
            total += count
        except Exception as e:
            print(f"  • {t:<26} : ERROR ({e})")
    print("-" * 55)
    print(f"  TOTAL RECORDS LOADED        : {total:>8,} rows")
    print("=" * 55 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Ingest NSE Datasets into MySQL 8.0")
    parser.add_argument("--host", default=os.environ.get("MYSQL_HOST", "localhost"), help="MySQL Host")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MYSQL_PORT", 3306)), help="MySQL Port")
    parser.add_argument("--user", default=os.environ.get("MYSQL_USER", "root"), help="MySQL User")
    parser.add_argument("--password", default=os.environ.get("MYSQL_PASSWORD", ""), help="MySQL Password")
    parser.add_argument("--database", default=os.environ.get("MYSQL_DATABASE", "youralgo"), help="Target Database Name")
    parser.add_argument("--data-dir", default=DEFAULT_NSE_DIR, help="Path to NSE data folder")
    parser.add_argument("--limit-credit", type=int, default=50000, help="Max rows to ingest from Credit_Rating_Details.csv (0 for all)")

    args = parser.parse_args()

    print("\n" + "=" * 55)
    print("  NSE DATA -> MYSQL 8.0 INGESTION PIPELINE")
    print("=" * 55)
    print(f"[*] Target Host    : {args.host}:{args.port}")
    print(f"[*] MySQL User     : {args.user}")
    print(f"[*] Target Database: {args.database}")
    print(f"[*] Data Directory : {args.data_dir}")

    # Connect to MySQL Server (without specifying DB first to allow DB creation)
    try:
        conn = pymysql.connect(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            charset="utf8mb4",
            autocommit=False
        )
        print("[✓] Connected to MySQL successfully.")
    except Exception as e:
        print(f"\n[!] Failed to connect to MySQL: {e}")
        print("\nTip: Provide credentials using:")
        print(f"  python ingest_nse_to_mysql.py --user {args.user} --password <YOUR_PASSWORD>")
        print("  or set MYSQL_PASSWORD in your environment.\n")
        sys.exit(1)

    try:
        t0 = time.time()
        create_database_and_tables(conn, args.database)

        print("\n[*] Starting dataset ingestion...")
        ingest_equities(conn, args.data_dir)
        ingest_etfs(conn, args.data_dir)
        ingest_sme(conn, args.data_dir)
        ingest_corporate_actions(conn, args.data_dir)
        ingest_credit_ratings(conn, args.data_dir, max_rows=args.limit_credit)
        ingest_debt(conn, args.data_dir)
        ingest_name_changes(conn, args.data_dir)
        ingest_symbol_changes(conn, args.data_dir)
        ingest_slb(conn, args.data_dir)

        elapsed = time.time() - t0
        print(f"\n[✓] Ingestion finished in {elapsed:.2f} seconds.")
        print_summary_report(conn, args.database)

    finally:
        conn.close()

if __name__ == "__main__":
    main()
