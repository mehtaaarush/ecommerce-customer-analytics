-- Two comparable 12-month years: KPIs and the share of customers who ordered more than once.
WITH tagged AS (
    SELECT
        *,
        CASE
            WHEN invoice_date >= $year1_start AND invoice_date < $year1_end THEN 'year1'
            WHEN invoice_date >= $year2_start AND invoice_date < $year2_end THEN 'year2'
        END AS period
    FROM lines
    WHERE status IN ('sale', 'cancellation')
),
customer_orders AS (
    SELECT period, customer_id, COUNT(DISTINCT invoice) AS orders
    FROM tagged
    WHERE status = 'sale' AND customer_id IS NOT NULL AND period IS NOT NULL
    GROUP BY period, customer_id
),
repeat_rates AS (
    SELECT period, AVG(CASE WHEN orders >= 2 THEN 1.0 ELSE 0.0 END) AS repeat_rate
    FROM customer_orders
    GROUP BY period
)
SELECT
    t.period,
    SUM(t.amount) AS net_revenue,
    SUM(t.amount) FILTER (WHERE t.status = 'sale') AS gross_sales,
    COUNT(DISTINCT t.invoice) FILTER (WHERE t.status = 'sale') AS orders,
    COUNT(DISTINCT t.customer_id) FILTER (WHERE t.status = 'sale') AS customers,
    ANY_VALUE(r.repeat_rate) AS repeat_rate
FROM tagged AS t
JOIN repeat_rates AS r USING (period)
WHERE t.period IS NOT NULL
GROUP BY t.period
ORDER BY t.period;
