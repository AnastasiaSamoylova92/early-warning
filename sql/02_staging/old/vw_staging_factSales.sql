CREATE OR ALTER VIEW staging.factSales AS

SELECT

    sales_id,
    order_id,
    date_id,

    CAST([date] AS DATE) AS order_date,

    CAST(year_month AS DATE) AS year_month,

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
    END AS order_size_category

FROM raw.factSales;

SELECT TOP 10 * from staging.factSales;

