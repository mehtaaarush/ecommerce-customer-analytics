-- Net revenue, orders and customers by country.
SELECT
    country,
    SUM(amount) AS net_revenue,
    COUNT(DISTINCT invoice) FILTER (WHERE status = 'sale') AS orders,
    COUNT(DISTINCT customer_id) FILTER (WHERE status = 'sale') AS customers
FROM lines
WHERE status IN ('sale', 'cancellation')
GROUP BY country
ORDER BY net_revenue DESC;
