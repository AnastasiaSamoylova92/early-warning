

DROP TABLE IF EXISTS raw.factPipeline;
DROP TABLE IF EXISTS raw.factReturns;
DROP TABLE IF EXISTS raw.factCRMActivities;
DROP TABLE IF EXISTS raw.factCosts;
DROP TABLE IF EXISTS raw.factInventory;
DROP TABLE IF EXISTS raw.factForecast;
DROP TABLE IF EXISTS raw.factSales;
DROP TABLE IF EXISTS raw.dimSalesRep;
DROP TABLE IF EXISTS raw.dimCustomer;
DROP TABLE IF EXISTS raw.dimProduct;
DROP TABLE IF EXISTS raw.dimRegion;
DROP TABLE IF EXISTS raw.dimDate;
GO

CREATE TABLE raw.dimDate (
    date_id INT,
    [date] DATE,
    [year] SMALLINT,
    [quarter] TINYINT,
    [month] TINYINT,
    month_name VARCHAR(20),

    year_month DATE,

    day_of_week TINYINT,

    week_of_year TINYINT,

    is_month_end BIT,

    is_quarter_end BIT
);

CREATE TABLE raw.dimRegion (
    region_id INT,
    country VARCHAR(100),
    region VARCHAR(100),
    currency CHAR(3),
    fx_to_eur DECIMAL(18,6),
    market_growth_factor DECIMAL(9,6),
    margin_factor DECIMAL(9,6)
);

CREATE TABLE raw.dimProduct (
    product_id INT,
    sku VARCHAR(50),
    product_family VARCHAR(100),
    product_group VARCHAR(100),
    product_name VARCHAR(255),
    launch_year SMALLINT,
    lifecycle_stage VARCHAR(50),
    base_list_price_eur DECIMAL(18,2),
    base_unit_cost_eur DECIMAL(18,2),
    target_margin_pct DECIMAL(9,6),
    product_growth_factor DECIMAL(9,6)
);

CREATE TABLE raw.dimCustomer (
    customer_id INT,
    customer_code VARCHAR(50),
    customer_segment VARCHAR(50),
    industry VARCHAR(100),
    region_id INT,
    customer_since DATE,
    customer_size_score DECIMAL(18,6),
    base_churn_probability DECIMAL(9,6)
);

CREATE TABLE raw.dimSalesRep (
    sales_rep_id INT,
    sales_rep_code VARCHAR(50),
    region_id INT,
    seniority VARCHAR(50),
    annual_quota_eur DECIMAL(18,2)
);

CREATE TABLE raw.factSales (
    sales_id BIGINT,
    order_id VARCHAR(50),
    date_id INT,
    [date] DATE,
    year_month VARCHAR(50),
    customer_id INT,
    product_id INT,
    region_id INT,
    sales_rep_id INT NULL,
    units INT,
    asp_eur DECIMAL(18,4),
    discount_pct DECIMAL(9,6),
    revenue_eur DECIMAL(18,2),
    revenue_local_currency DECIMAL(18,2),
    currency CHAR(3),
    unit_cost_eur DECIMAL(18,4),
    gross_profit_eur DECIMAL(18,2),
    gross_margin_pct DECIMAL(9,6),
    is_outlier_order BIT
);

CREATE TABLE raw.factForecast (
    forecast_id BIGINT,
    year_month DATE,
    product_id INT,
    region_id INT,
    forecast_version VARCHAR(50),
    forecast_units INT,
    forecast_revenue_eur DECIMAL(18,2),
    actual_units INT,
    actual_revenue_eur DECIMAL(18,2)
);

CREATE TABLE raw.factInventory (
    inventory_id BIGINT,
    year_month DATE,
    product_id INT,
    region_id INT,
    opening_stock_units INT,
    production_units INT,
    ending_stock_units INT,
    stockout_flag BIT,
    inventory_value_eur DECIMAL(18,2)
);

CREATE TABLE raw.factCosts (
    cost_id BIGINT,
    year_month DATE,
    product_id INT,
    standard_unit_cost_eur DECIMAL(18,4),
    actual_unit_cost_eur DECIMAL(18,4)
);

CREATE TABLE raw.factCRMActivities (
    activity_id BIGINT,
    date_id INT,
    [date] DATE,
    customer_id INT,
    sales_rep_id INT,
    activity_type VARCHAR(50),
    activity_minutes INT,
    sentiment_score DECIMAL(9,6),
    customer_health_score DECIMAL(9,2)
);

CREATE TABLE raw.factReturns (
    return_id BIGINT,
    sales_id BIGINT,
    date_id INT,
    [date] DATE,
    customer_id INT,
    product_id INT,
    region_id INT,
    return_units INT,
    return_value_eur DECIMAL(18,2),
    return_reason VARCHAR(100)
);

CREATE TABLE raw.factPipeline (
    opportunity_id BIGINT,
    created_date DATE,
    customer_id INT,
    product_group VARCHAR(100),
    sales_rep_id INT,
    stage VARCHAR(50),
    expected_value_eur DECIMAL(18,2),
    win_probability DECIMAL(9,6),
    expected_close_date DATE,
    created_date_id INT,
    weighted_pipeline_eur DECIMAL(18,2)
);