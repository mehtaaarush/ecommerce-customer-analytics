-- Co-occurrence of the most-ordered products within the same invoice (market basket analysis).
WITH baskets AS (
    SELECT DISTINCT invoice, stock_code
    FROM lines
    WHERE status = 'sale'
),
total AS (
    SELECT COUNT(DISTINCT invoice) AS invoices FROM baskets
),
item_counts AS (
    SELECT stock_code, COUNT(*) AS invoices
    FROM baskets
    GROUP BY stock_code
),
top_items AS (
    SELECT stock_code FROM item_counts ORDER BY invoices DESC, stock_code LIMIT $top_n
),
top_baskets AS (
    SELECT * FROM baskets WHERE stock_code IN (SELECT stock_code FROM top_items)
),
pairs AS (
    SELECT a.stock_code AS item_a, b.stock_code AS item_b, COUNT(*) AS together
    FROM top_baskets AS a
    JOIN top_baskets AS b ON a.invoice = b.invoice AND a.stock_code < b.stock_code
    GROUP BY item_a, item_b
    HAVING COUNT(*) >= $min_together
)
SELECT
    p.item_a,
    p.item_b,
    p.together,
    ca.invoices AS invoices_a,
    cb.invoices AS invoices_b,
    t.invoices AS total_invoices
FROM pairs AS p
JOIN item_counts AS ca ON ca.stock_code = p.item_a
JOIN item_counts AS cb ON cb.stock_code = p.item_b
CROSS JOIN total AS t
ORDER BY p.together DESC;
