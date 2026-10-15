# 📊 NSE Data Warehouse to MySQL 8.0 Ingestion Guide

This toolkit provides an automated migration pipeline and SQL schema to load official **National Stock Exchange of India (NSE)** datasets into **MySQL 8.0+**.

---

## 📁 Files Created

1. **`ingest_nse_to_mysql.py`** ([link](file:///c:/Users/patel/Desktop/Algo%20Trading/ingest_nse_to_mysql.py)): Automated Python ETL ingestion script with batching, type sanitation, and progress reporting.
2. **`schema_nse_data.sql`** ([link](file:///c:/Users/patel/Desktop/Algo%20Trading/schema_nse_data.sql)): Raw DDL schema file for creating the `nse_data` database and normalized tables directly in MySQL.
3. Mirror script available at: `YourAlgo-v2/backend/ingest_nse_to_mysql.py`.

---

## 🗄️ Relational Schema & Tables

| Table | Source File | Records | Key Fields & Indexes |
|---|---|---|---|
| **`nse_equities`** | `EQUITY_L.csv` | ~2,603 | `symbol` (PK), `company_name`, `series`, `paid_up_value`, `isin`, `face_value`, `sector` |
| **`nse_etfs`** | `eq_etfseclist.csv` | ~352 | `symbol` (PK), `security_name`, `underlying_asset`, `category`, `isin`, `face_value` |
| **`nse_sme_equities`** | `SME_EQUITY_L.csv` | ~579 | `symbol` (PK), `company_name`, `series`, `listing_date`, `isin`, `face_value` |
| **`nse_corporate_actions`** | `CDC_Record_Date_Details_0.csv` | ~150+ | `id` (PK), `company_name`, `purpose`, `record_date`, `payment_date`, `isin` |
| **`nse_credit_ratings`** | `Credit_Rating_Details.csv` | Configurable | `id` (PK), `symbol`, `company_name`, `agency`, `credit_rating`, `rating_action`, `outlook` |
| **`nse_debt_securities`** | `DEBT.csv` | ~3,000+ | `id` (PK), `symbol`, `company_name`, `series`, `face_value`, `redemption_date`, `ip_rate` |
| **`nse_name_changes`** | `namechange.csv` | ~2,500+ | `id` (PK), `symbol`, `prev_name`, `new_name`, `change_date` |
| **`nse_symbol_changes`** | `symbolchange.csv` | ~700+ | `id` (PK), `company_name`, `old_symbol`, `new_symbol`, `change_date` |
| **`nse_slb_eligible`** | `slb_elg_sec.csv` | ~800+ | `id` (PK), `symbol`, `series`, `normal_eligibility`, `market_type` |

---

## 🚀 How to Run the Ingestion

### Option A: Using the Python Ingestion Pipeline

Open your PowerShell / terminal and run:

```bash
# Run with your MySQL root password:
python ingest_nse_to_mysql.py --user root --password YOUR_MYSQL_PASSWORD

# Or if you created a dedicated 'youralgo' user:
python ingest_nse_to_mysql.py --user youralgo --password youralgo

# Custom database name or port:
python ingest_nse_to_mysql.py --user root --password YOUR_MYSQL_PASSWORD --database nse_data --port 3306
```

#### CLI Parameters:
* `--host`: MySQL host (default: `localhost`)
* `--port`: MySQL port (default: `3306`)
* `--user`: MySQL username (default: `root`)
* `--password`: MySQL password (default: `""` or read from `MYSQL_PASSWORD` env var)
* `--database`: Target database (default: `nse_data`, created automatically if not present)
* `--data-dir`: Path to NSE data folder (default: `c:\Users\patel\Desktop\Algo Trading\NSE data`)
* `--limit-credit`: Number of rows to ingest from the 135 MB Credit Ratings file (default: `50000`, set `0` for full dataset)

---

### Option B: Running the DDL Directly in MySQL

If you prefer to create tables manually via MySQL Workbench or the `mysql` CLI:

```bash
mysql -u root -p < "c:\Users\patel\Desktop\Algo Trading\schema_nse_data.sql"
```

---

## 🔍 Useful SQL Queries on the Ingested Warehouse

Once ingested, you can query your data warehouse in MySQL:

### 1. View Top Equities by Sector
```sql
USE nse_data;

SELECT sector, COUNT(*) AS total_stocks
FROM nse_equities
GROUP BY sector
ORDER BY total_stocks DESC;
```

### 2. Search Upcoming Corporate Record Dates (Dividends, Splits, Bonus)
```sql
SELECT company_name, purpose, record_date, isin
FROM nse_corporate_actions
WHERE purpose LIKE '%DIVIDEND%' OR purpose LIKE '%BONUS%'
ORDER BY record_date DESC
LIMIT 20;
```

### 3. Credit Rating Upgrades from CRISIL / ICRA
```sql
SELECT company_name, symbol, agency, credit_rating, rating_action, outlook, reporting_date
FROM nse_credit_ratings
WHERE rating_action LIKE '%Upgrade%' OR rating_action LIKE '%Positive%'
ORDER BY id DESC
LIMIT 25;
```

### 4. Cross-Reference Ticker Symbol Changes
```sql
SELECT c.company_name, c.old_symbol, c.new_symbol, c.change_date, e.sector
FROM nse_symbol_changes c
LEFT JOIN nse_equities e ON c.new_symbol = e.symbol
ORDER BY c.change_date DESC
LIMIT 20;
```
