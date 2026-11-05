-- Net revenue, units and reach per product, labelled with each code's most common description.
WITH names AS (
    SELECT
        stock_code,
        description,
        ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY COUNT(*) DESC, description) AS name_rank
    FROM lines
    WHERE status = 'sale' AND description IS NOT NULL
    GROUP BY stock_code, description
)
SELECT
    l.stock_code,
    n.description,
    SUM(l.amount) AS net_revenue,
    SUM(l.quantity) AS net_units,
    COUNT(DISTINCT l.invoice) FILTER (WHERE l.status = 'sale') AS orders,
    COUNT(DISTINCT l.customer_id) FILTER (WHERE l.status = 'sale') AS customers
FROM lines AS l
JOIN names AS n ON n.stock_code = l.stock_code AND n.name_rank = 1
WHERE l.status IN ('sale', 'cancellation')
GROUP BY l.stock_code, n.description
ORDER BY net_revenue DESC;
