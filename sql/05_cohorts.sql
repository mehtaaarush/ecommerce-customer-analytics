-- Monthly acquisition cohorts: customers active (and their net revenue) N months after their first purchase.
-- Only complete months (before $end) are used, so the latest diagonal is not understated.
WITH firsts AS (
    SELECT customer_id, date_trunc('month', MIN(invoice_date)) AS cohort
    FROM lines
    WHERE status = 'sale' AND customer_id IS NOT NULL AND invoice_date < $end
    GROUP BY customer_id
),
activity AS (
    SELECT customer_id, date_trunc('month', invoice_date) AS month, SUM(amount) AS revenue
    FROM lines
    WHERE status IN ('sale', 'cancellation') AND customer_id IS NOT NULL AND invoice_date < $end
    GROUP BY customer_id, month
    HAVING COUNT(*) FILTER (WHERE status = 'sale') > 0
)
SELECT
    f.cohort,
    date_diff('month', f.cohort, a.month) AS months_since,
    COUNT(*) AS active_customers,
    SUM(a.revenue) AS revenue
FROM firsts AS f
JOIN activity AS a USING (customer_id)
GROUP BY f.cohort, months_since
ORDER BY f.cohort, months_since;
