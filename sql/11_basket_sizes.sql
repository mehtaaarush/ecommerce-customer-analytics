-- How many distinct products a completed order contains.
WITH sizes AS (
    SELECT invoice, COUNT(DISTINCT stock_code) AS products
    FROM lines
    WHERE status = 'sale'
    GROUP BY invoice
)
SELECT
    COUNT(*) AS orders,
    AVG(products) AS mean_products,
    MEDIAN(products) AS median_products,
    AVG(CASE WHEN products >= 2 THEN 1.0 ELSE 0.0 END) AS multi_product_share
FROM sizes;
