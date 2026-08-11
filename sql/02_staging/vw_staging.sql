USE RevenueAnalytics;
GO

CREATE OR ALTER VIEW staging.factSales AS

SELECT

    sales_id,
    order_id,
    date_id,

    CAST([date] AS DATE) AS order_date,

    CAST(year_month + '-01' AS DATE) AS year_month,

    customer_id,
    product_id,
    region_id,
    sales_rep_id,

    units,
    asp_eur,
    discount_pct,
    revenue_eur,
    revenue_local_currency,

    currency,

    unit_cost_eur,
    gross_profit_eur,
    gross_margin_pct,

    is_outlier_order,

    ---------------------------------
    -- Derived Metrics
    ---------------------------------

    revenue_eur - gross_profit_eur AS cogs_eur,

    revenue_eur * discount_pct AS discount_value_eur,

    CASE
        WHEN gross_margin_pct >= 0.40 THEN 'High Margin'
        WHEN gross_margin_pct >= 0.25 THEN 'Medium Margin'
        ELSE 'Low Margin'
    END AS margin_category,

    CASE 
        WHEN units >= 100 THEN 'Large Order'
        WHEN units >= 25 THEN 'Medium Order'
        ELSE 'Small Order'
    END AS order_size_category,

    CASE
        WHEN sales_rep_id IS NULL THEN 1
        ELSE 0
    END AS missing_sales_rep_flag,

    CASE    
        WHEN discount_pct IS NULL THEN 1
        ELSE 0
    END AS missing_discount_flag,

    CASE
        WHEN gross_margin_pct IS NULL THEN 1
        ELSE 0
    END AS missing_margin_flag
FROM dbo.factSales;

CREATE OR ALTER VIEW staging.dimRegion AS
SELECT
    TRY_CAST(region_id AS INT) AS region_id,
    LTRIM(RTRIM(country)) AS country,
    LTRIM(RTRIM(region)) AS region,
    UPPER(LTRIM(RTRIM(currency))) AS currency,
    TRY_CAST(fx_to_eur AS DECIMAL(18,6)) AS fx_to_eur,
    TRY_CAST(market_growth_factor AS DECIMAL(9,6)) AS market_growth_factor,
    TRY_CAST(margin_factor AS DECIMAL(9,6)) AS margin_factor
FROM dbo.dimRegion;

SELECT TOP 10 * FROM staging.dimRegion;

CREATE OR ALTER VIEW staging.dimProduct AS
SELECT
    TRY_CAST(product_id AS INT) AS product_id,
    UPPER(LTRIM(RTRIM(sku))) AS sku,
    LTRIM(RTRIM(product_family)) AS product_family,
    LTRIM(RTRIM(product_group)) AS product_group,
    LTRIM(RTRIM(product_name)) AS product_name,
    TRY_CAST(launch_year AS SMALLINT) AS launch_year,
    LTRIM(RTRIM(lifecycle_stage)) AS lifecycle_stage,
    TRY_CAST(base_list_price_eur AS DECIMAL(18,2)) AS base_list_price_eur,
    TRY_CAST(base_unit_cost_eur AS DECIMAL(18,2)) AS base_unit_cost_eur,
    TRY_CAST(target_margin_pct AS DECIMAL(9,6)) AS target_margin_pct,
    TRY_CAST(product_growth_factor AS DECIMAL(9,6)) AS product_growth_factor,

    CASE 
        WHEN lifecycle_stage = 'Decline' THEN 1 
        ELSE 0 
    END AS is_declining_product,

    CASE 
        WHEN lifecycle_stage = 'New' THEN 1 
        ELSE 0 
    END AS is_new_product
FROM dbo.dimProduct;

SELECT TOP 10 * FROM staging.dimProduct;

CREATE OR ALTER VIEW staging.dimCustomer AS
SELECT
    TRY_CAST(customer_id AS INT) AS customer_id,
    UPPER(LTRIM(RTRIM(customer_code))) AS customer_code,
    LTRIM(RTRIM(customer_segment)) AS customer_segment,
    LTRIM(RTRIM(industry)) AS industry,
    TRY_CAST(region_id AS INT) AS region_id,
    TRY_CAST(customer_since AS DATE) AS customer_since,
    TRY_CAST(customer_size_score AS DECIMAL(18,6)) AS customer_size_score,
    TRY_CAST(base_churn_probability AS DECIMAL(9,6)) AS base_churn_probability,

    CASE
        WHEN TRY_CAST(base_churn_probability AS DECIMAL(9,6)) >= 0.12 THEN 'High Churn Risk'
        WHEN TRY_CAST(base_churn_probability AS DECIMAL(9,6)) >= 0.07 THEN 'Medium Churn Risk'
        ELSE 'Low Churn Risk'
    END AS churn_risk_band
FROM dbo.dimCustomer;

SELECT TOP 10 * FROM staging.dimCustomer;

CREATE OR ALTER VIEW staging.dimSalesRep AS
SELECT
    TRY_CAST(sales_rep_id AS INT) AS sales_rep_id,
    UPPER(LTRIM(RTRIM(sales_rep_code))) AS sales_rep_code,
    TRY_CAST(region_id AS INT) AS region_id,
    LTRIM(RTRIM(seniority)) AS seniority,
    TRY_CAST(annual_quota_eur AS DECIMAL(18,2)) AS annual_quota_eur
FROM dbo.dimSalesRep;

SELECT TOP 10 * FROM staging.dimSalesRep;

CREATE OR ALTER VIEW staging.factForecast AS
SELECT
    TRY_CAST(forecast_id AS BIGINT) AS forecast_id,
    CAST(year_month + '-01' AS DATE) AS year_month,
    TRY_CAST(product_id AS INT) AS product_id,
    TRY_CAST(region_id AS INT) AS region_id,
    LTRIM(RTRIM(forecast_version)) AS forecast_version,
    TRY_CAST(forecast_units AS INT) AS forecast_units,
    TRY_CAST(forecast_revenue_eur AS DECIMAL(18,2)) AS forecast_revenue_eur,
    TRY_CAST(actual_units AS INT) AS actual_units,
    TRY_CAST(actual_revenue_eur AS DECIMAL(18,2)) AS actual_revenue_eur,

    TRY_CAST(forecast_revenue_eur AS DECIMAL(18,2))
        - TRY_CAST(actual_revenue_eur AS DECIMAL(18,2)) AS forecast_error_eur,

    CASE 
        WHEN TRY_CAST(actual_revenue_eur AS DECIMAL(18,2)) = 0 THEN NULL
        ELSE
            (
                TRY_CAST(forecast_revenue_eur AS DECIMAL(18,2))
                - TRY_CAST(actual_revenue_eur AS DECIMAL(18,2))
            )
            / TRY_CAST(actual_revenue_eur AS DECIMAL(18,2))
    END AS forecast_error_pct
FROM dbo.factForecast;


CREATE OR ALTER VIEW staging.factInventory AS
SELECT
    TRY_CAST(inventory_id AS BIGINT) AS inventory_id,
    CAST(year_month + '-01' AS DATE) AS year_month,
    TRY_CAST(product_id AS INT) AS product_id,
    TRY_CAST(region_id AS INT) AS region_id,
    TRY_CAST(opening_stock_units AS INT) AS opening_stock_units,
    TRY_CAST(production_units AS INT) AS production_units,
    TRY_CAST(ending_stock_units AS INT) AS ending_stock_units,
    TRY_CAST(stockout_flag AS BIT) AS stockout_flag,
    TRY_CAST(inventory_value_eur AS DECIMAL(18,2)) AS inventory_value_eur,

    CASE 
        WHEN TRY_CAST(ending_stock_units AS INT) <= 0 THEN 1 
        ELSE 0 
    END AS zero_stock_flag
FROM dbo.factInventory;

SELECT TOP 10 * FROM staging.factInventory;

CREATE OR ALTER VIEW staging.factCosts AS
SELECT
    TRY_CAST(cost_id AS BIGINT) AS cost_id,
    CAST(year_month + '-01' AS DATE) AS year_month,
    TRY_CAST(product_id AS INT) AS product_id,
    TRY_CAST(standard_unit_cost_eur AS DECIMAL(18,4)) AS standard_unit_cost_eur,
    TRY_CAST(actual_unit_cost_eur AS DECIMAL(18,4)) AS actual_unit_cost_eur,

    TRY_CAST(actual_unit_cost_eur AS DECIMAL(18,4))
        - TRY_CAST(standard_unit_cost_eur AS DECIMAL(18,4)) AS cost_variance_eur,

    CASE
        WHEN TRY_CAST(standard_unit_cost_eur AS DECIMAL(18,4)) = 0 THEN NULL
        ELSE
            (
                TRY_CAST(actual_unit_cost_eur AS DECIMAL(18,4))
                - TRY_CAST(standard_unit_cost_eur AS DECIMAL(18,4))
            )
            / TRY_CAST(standard_unit_cost_eur AS DECIMAL(18,4))
    END AS cost_variance_pct
FROM dbo.factCosts;

SELECT TOP 10 * FROM staging.factCosts;

CREATE OR ALTER VIEW staging.factCRMActivities AS
SELECT
    TRY_CAST(activity_id AS BIGINT) AS activity_id,
    TRY_CAST(date_id AS INT) AS date_id,
    TRY_CAST([date] AS DATE) AS activity_date,
    TRY_CAST(customer_id AS INT) AS customer_id,
    TRY_CAST(sales_rep_id AS INT) AS sales_rep_id,
    LTRIM(RTRIM(activity_type)) AS activity_type,
    TRY_CAST(activity_minutes AS INT) AS activity_minutes,
    TRY_CAST(sentiment_score AS DECIMAL(9,6)) AS sentiment_score,
    TRY_CAST(customer_health_score AS DECIMAL(9,2)) AS customer_health_score,

    CASE
        WHEN TRY_CAST(customer_health_score AS DECIMAL(9,2)) >= 75 THEN 'Healthy'
        WHEN TRY_CAST(customer_health_score AS DECIMAL(9,2)) >= 50 THEN 'Neutral'
        ELSE 'At Risk'
    END AS customer_health_band
FROM dbo.factCRMActivities;

SELECT TOP 10 * FROM staging.factCRMActivities;

CREATE OR ALTER VIEW staging.factReturns AS
SELECT
    TRY_CAST(return_id AS BIGINT) AS return_id,
    TRY_CAST(sales_id AS BIGINT) AS sales_id,
    TRY_CAST(date_id AS INT) AS date_id,
    TRY_CAST([date] AS DATE) AS return_date,
    TRY_CAST(customer_id AS INT) AS customer_id,
    TRY_CAST(product_id AS INT) AS product_id,
    TRY_CAST(region_id AS INT) AS region_id,
    TRY_CAST(return_units AS INT) AS return_units,
    TRY_CAST(return_value_eur AS DECIMAL(18,2)) AS return_value_eur,
    LTRIM(RTRIM(return_reason)) AS return_reason
FROM dbo.factReturns;

SELECT TOP 10 * FROM staging.factReturns;

CREATE OR ALTER VIEW staging.factPipeline AS
SELECT
    TRY_CAST(opportunity_id AS BIGINT) AS opportunity_id,
    TRY_CAST(created_date AS DATE) AS created_date,
    TRY_CAST(customer_id AS INT) AS customer_id,
    LTRIM(RTRIM(product_group)) AS product_group,
    TRY_CAST(sales_rep_id AS INT) AS sales_rep_id,
    LTRIM(RTRIM(stage)) AS stage,
    TRY_CAST(expected_value_eur AS DECIMAL(18,2)) AS expected_value_eur,
    TRY_CAST(win_probability AS DECIMAL(9,6)) AS win_probability,
    TRY_CAST(expected_close_date AS DATE) AS expected_close_date,
    TRY_CAST(created_date_id AS INT) AS created_date_id,
    TRY_CAST(weighted_pipeline_eur AS DECIMAL(18,2)) AS weighted_pipeline_eur,

    DATEDIFF(
        DAY,
        TRY_CAST(created_date AS DATE),
        TRY_CAST(expected_close_date AS DATE)
    ) AS days_to_close,

    CASE
        WHEN stage = 'Closed Won' THEN 1
        ELSE 0
    END AS is_closed_won,

    CASE
        WHEN stage = 'Closed Lost' THEN 1
        ELSE 0
    END AS is_closed_lost
FROM dbo.factPipeline;

SELECT TOP 10 * FROM staging.factPipeline;

CREATE OR ALTER VIEW staging.factMarketSignals AS
SELECT
    CAST(year_month + '-01' AS DATE) AS year_month,
    TRY_CAST(region_id  AS INT) AS region_id ,
    LTRIM(RTRIM(product_family )) AS product_family,
    LTRIM(RTRIM(product_group  )) AS product_group,
    TRY_CAST(market_demand_index AS DECIMAL(9,2)) AS market_demand_index,
    TRY_CAST(market_growth_pct AS DECIMAL(9,2)) AS market_growth_pct,
    TRY_CAST(competitor_pressure_index AS DECIMAL(9,2)) AS competitor_pressure_index,
    TRY_CAST(seasonality_index AS DECIMAL(9,2)) AS seasonality_index,
    TRY_CAST(macro_business_index  AS DECIMAL(9,2)) AS macro_business_index,
    TRY_CAST(supply_pressure_index  AS DECIMAL(9,2)) AS supply_pressure_index ,
    TRY_CAST(pipeline_interest_index  AS DECIMAL(9,2)) AS pipeline_interest_index ,

    TRY_CAST(demand_shock_flag  AS BIT) AS demand_shock_flag,

    TRY_CAST(market_opportunity_score   AS DECIMAL(9,2)) AS market_opportunity_score  ,
    TRY_CAST(regional_market_growth_factor   AS DECIMAL(9,2)) AS regional_market_growth_factor

FROM dbo.factMarketSignals;

CREATE OR ALTER VIEW staging.factMarketActivities AS
SELECT
    CAST(year_month + '-01' AS DATE) AS year_month,

    TRY_CAST(region_id  AS INT) AS region_id ,
    TRY_CAST(product_id   AS INT) AS product_id,

    TRY_CAST(campaign_flag   AS BIT) AS campaign_flag ,
    LTRIM(RTRIM(campaign_channel )) AS campaign_channel,

    TRY_CAST(campaign_spend_eur AS DECIMAL(18,2)) AS campaign_spend_eur,
    TRY_CAST(campaign_impressions  AS INT) AS campaign_impressions ,
    TRY_CAST(campaign_clicks   AS INT) AS campaign_clicks,
    TRY_CAST(campaign_ctr_pct AS DECIMAL(9,3)) AS campaign_ctr_pct,

    TRY_CAST(website_visits   AS INT) AS website_visits  ,
    TRY_CAST(product_page_views    AS INT) AS product_page_views ,
    TRY_CAST(demo_requests   AS INT) AS demo_requests  ,
    TRY_CAST(marketing_qualified_leads    AS INT) AS marketing_qualified_leads ,

    TRY_CAST(cost_per_lead_eur  AS DECIMAL(18,2)) AS cost_per_lead_eur,

    TRY_CAST(regional_crm_activity_index  AS DECIMAL(9,2)) AS regional_crm_activity_index ,
    TRY_CAST(pipeline_interest_index   AS DECIMAL(9,2)) AS pipeline_interest_index

FROM dbo.factMarketActivities;

SELECT TOP  10 * from staging.factMarketSignals;

SELECT TOP 10 * FROM dbo.factMarketActivities;