-- DDL di riferimento per la tabella "transactions" del database RetailAnalysis.
-- Creata automaticamente da sql/load_to_sqlserver.py; questo file serve solo come
-- riferimento/documentazione dello schema, non viene eseguito dalla pipeline.

USE RetailAnalysis;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.tables WHERE name = 'transactions' AND schema_id = SCHEMA_ID('dbo')
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
GO
