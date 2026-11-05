-- Monthly trading KPIs. Revenue is net of cancellations; orders and customers count completed sales.
-- A customer is "new" in the month of their first purchase in the data.
WITH first_purchase AS (
    SELECT customer_id, date_trunc('month', MIN(invoice_date)) AS first_month
    FROM lines
    WHERE status = 'sale' AND customer_id IS NOT NULL
    GROUP BY customer_id
),
tagged AS (
    SELECT
        l.*,
        date_trunc('month', l.invoice_date) AS month,
        CASE
            WHEN l.customer_id IS NULL THEN 'guest'
            WHEN f.first_month = date_trunc('month', l.invoice_date) THEN 'new'
            ELSE 'returning'
        END AS customer_type
    FROM lines AS l
    LEFT JOIN first_purchase AS f USING (customer_id)
    WHERE l.status IN ('sale', 'cancellation')
)
SELECT
    month,
    SUM(amount) AS net_revenue,
    SUM(amount) FILTER (WHERE status = 'sale') AS gross_sales,
    -COALESCE(SUM(amount) FILTER (WHERE status = 'cancellation'), 0) AS cancelled,
    COUNT(DISTINCT invoice) FILTER (WHERE status = 'sale') AS orders,
    COUNT(DISTINCT customer_id) FILTER (WHERE status = 'sale') AS customers,
    COUNT(DISTINCT customer_id) FILTER (WHERE status = 'sale' AND customer_type = 'new') AS new_customers,
    COALESCE(SUM(amount) FILTER (WHERE customer_type = 'new'), 0) AS revenue_new,
    COALESCE(SUM(amount) FILTER (WHERE customer_type = 'returning'), 0) AS revenue_returning,
    COALESCE(SUM(amount) FILTER (WHERE customer_type = 'guest'), 0) AS revenue_guest
FROM tagged
GROUP BY month
ORDER BY month;
