-- When orders are placed: completed orders by ISO weekday (1 = Monday) and hour.
WITH orders AS (
    SELECT invoice, MIN(invoice_date) AS ts, SUM(amount) AS value
    FROM lines
    WHERE status = 'sale'
    GROUP BY invoice
)
SELECT isodow(ts) AS weekday, hour(ts) AS hour, COUNT(*) AS orders, SUM(value) AS revenue
FROM orders
GROUP BY weekday, hour
ORDER BY weekday, hour;
