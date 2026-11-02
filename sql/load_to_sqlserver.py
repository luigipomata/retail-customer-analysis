"""
Carica il dataset pulito di Online Retail II (data/processed/online_retail_clean.csv)
sul database SQL Server "RetailAnalysis", nella tabella dbo.transactions.

Parametri di connessione letti da .env (vedi .env.example per le variabili richieste).

Uso:
    python sql/load_to_sqlserver.py
"""
import os
import re
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import pyodbc
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "processed" / "online_retail_clean.csv"

load_dotenv(PROJECT_ROOT / ".env")

SERVER = os.environ["SQL_SERVER"]
DATABASE = os.environ["SQL_DATABASE"]
DRIVER = os.environ.get("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
TRUSTED_CONNECTION = os.environ.get("SQL_TRUSTED_CONNECTION", "yes").strip().lower() == "yes"
USERNAME = os.environ.get("SQL_USERNAME")
PASSWORD = os.environ.get("SQL_PASSWORD")

TABLE_COLUMNS = [
    "InvoiceNo", "StockCode", "Description", "Quantity",
    "InvoiceDate", "UnitPrice", "CustomerID", "Country",
]

# Il nome del database finisce interpolato direttamente in una DDL (CREATE DATABASE
# non è parametrizzabile lato driver): lo validiamo per evitare injection anche se
# la fonte è un .env locale e non un input utente.
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def build_connection_string(database: str) -> str:
    if not _SAFE_IDENTIFIER.match(database):
        raise ValueError(f"Nome database non valido: {database!r}")

    parts = [
        f"DRIVER={{{DRIVER}}}",
        f"SERVER={SERVER}",
        f"DATABASE={database}",
        "Encrypt=yes",
        "TrustServerCertificate=yes",
    ]
    if TRUSTED_CONNECTION:
        parts.append("Trusted_Connection=yes")
    else:
        if not USERNAME or not PASSWORD:
            raise ValueError(
                "SQL_USERNAME e SQL_PASSWORD sono richiesti quando SQL_TRUSTED_CONNECTION=no"
            )
        parts.append(f"UID={USERNAME}")
        parts.append(f"PWD={PASSWORD}")
    return ";".join(parts) + ";"


def ensure_database_exists() -> None:
    conn = pyodbc.connect(build_connection_string("master"), autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT database_id FROM sys.databases WHERE name = ?", DATABASE)
        if cursor.fetchone() is not None:
            print(f"Database '{DATABASE}' gia' esistente.")
        else:
            cursor.execute(f"CREATE DATABASE [{DATABASE}]")
            print(f"Database '{DATABASE}' creato.")
    finally:
        conn.close()


def ensure_table_exists() -> None:
    conn = pyodbc.connect(build_connection_string(DATABASE), autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1 FROM sys.tables
                WHERE name = 'transactions' AND schema_id = SCHEMA_ID('dbo')
            )
            BEGIN
                CREATE TABLE dbo.transactions (
                    InvoiceNo    VARCHAR(20)     NOT NULL,
                    StockCode    VARCHAR(20)     NOT NULL,
                    Description  NVARCHAR(255)   NULL,
                    Quantity     INT             NOT NULL,
                    InvoiceDate  DATETIME2       NOT NULL,
                    UnitPrice    DECIMAL(10, 4)  NOT NULL,
                    CustomerID   INT             NOT NULL,
                    Country      NVARCHAR(50)    NOT NULL
                );
            END
            """
        )
        print("Tabella 'dbo.transactions' verificata/creata.")
    finally:
        conn.close()


def load_clean_csv() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"CSV pulito non trovato in {CSV_PATH}. "
            "Esegui prima il notebook notebooks/01_eda/01_eda_online_retail.ipynb."
        )
    df = pd.read_csv(CSV_PATH, parse_dates=["InvoiceDate"])
    df = df.rename(columns={"Invoice": "InvoiceNo", "Price": "UnitPrice"})
    return df[TABLE_COLUMNS]


def load_into_sql(df: pd.DataFrame) -> None:
    odbc_connect = quote_plus(build_connection_string(DATABASE))
    engine = create_engine(
        f"mssql+pyodbc:///?odbc_connect={odbc_connect}", fast_executemany=True
    )
    try:
        with engine.begin() as connection:
            # Svuota la tabella prima di ricaricare, cosi' lo script e' ripetibile
            # senza generare righe duplicate ad ogni esecuzione.
            connection.execute(text("TRUNCATE TABLE dbo.transactions"))
        df.to_sql(
            "transactions",
            engine,
            schema="dbo",
            if_exists="append",
            index=False,
            chunksize=10_000,
        )
    finally:
        engine.dispose()


def main() -> None:
    print(f"Server: {SERVER} | Database: {DATABASE}")
    ensure_database_exists()
    ensure_table_exists()

    df = load_clean_csv()
    print(f"Righe da importare: {len(df):,}")

    load_into_sql(df)
    print("Import completato.")


if __name__ == "__main__":
    main()
