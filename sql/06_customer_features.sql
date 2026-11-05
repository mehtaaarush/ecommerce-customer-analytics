-- One row per customer with purchase history before $cutoff, plus what they did in the next $horizon days.
-- Features only see invoices dated before the cutoff; the label only sees the window after it.
-- Money sums are rounded to 6 decimals: DuckDB adds floats in parallel, so their last bits vary from run to run,
-- and rounding removes that noise (and nothing else) so the model sees identical features every time.
WITH history AS (
    SELECT *
    FROM lines
    WHERE customer_id IS NOT NULL AND status IN ('sale', 'cancellation') AND invoice_date < $cutoff
),
orders AS (
    SELECT customer_id, invoice, MIN(invoice_date) AS ts, ROUND(SUM(amount), 6) AS value, COUNT(DISTINCT stock_code) AS products
    FROM history
    WHERE status = 'sale'
    GROUP BY customer_id, invoice
),
order_stats AS (
    SELECT
        customer_id,
        date_diff('day', MAX(ts), $cutoff) AS recency_days,
        date_diff('day', MIN(ts), $cutoff) AS tenure_days,
        COUNT(*) AS frequency,
        ROUND(SUM(value), 6) / COUNT(*) AS avg_order_value,
        AVG(products) AS avg_products,
        COUNT(*) FILTER (WHERE ts >= $cutoff - INTERVAL 90 DAY) AS orders_90d,
        COUNT(*) FILTER (WHERE ts >= $cutoff - INTERVAL 180 DAY AND ts < $cutoff - INTERVAL 90 DAY) AS orders_prev_90d,
        -- the label window one year earlier: seasonal buyers (Christmas stock) come back in the same quarter
        COUNT(*) FILTER (WHERE ts >= $cutoff - INTERVAL 365 DAY
                           AND ts < $cutoff - INTERVAL 365 DAY + to_days(CAST($horizon AS INTEGER))) AS orders_same_window_last_year,
        COUNT(DISTINCT date_trunc('month', ts)) AS active_months
    FROM orders
    GROUP BY customer_id
),
money AS (
    SELECT
        customer_id,
        ROUND(SUM(amount), 6) AS monetary,
        COALESCE(ROUND(SUM(amount) FILTER (WHERE invoice_date >= $cutoff - INTERVAL 90 DAY), 6), 0) AS spend_90d,
        AVG(CASE WHEN status = 'cancellation' THEN 1.0 ELSE 0.0 END) AS cancel_share,
        COUNT(DISTINCT stock_code) AS distinct_products,
        MODE(country) AS country
    FROM history
    GROUP BY customer_id
),
future AS (
    SELECT
        customer_id,
        COUNT(DISTINCT invoice) FILTER (WHERE status = 'sale') AS future_orders,
        ROUND(SUM(amount), 6) AS future_revenue
    FROM lines
    WHERE customer_id IS NOT NULL
      AND status IN ('sale', 'cancellation')
      AND invoice_date >= $cutoff
      AND invoice_date < $cutoff + to_days(CAST($horizon AS INTEGER))
    GROUP BY customer_id
)
SELECT
    o.*,
    m.monetary,
    m.spend_90d,
    m.cancel_share,
    m.distinct_products,
    m.country,
    COALESCE(f.future_orders, 0) AS future_orders,
    COALESCE(f.future_revenue, 0) AS future_revenue
FROM order_stats AS o
JOIN money AS m USING (customer_id)
LEFT JOIN future AS f USING (customer_id)
ORDER BY customer_id;
