-- How the raw lines split across cleaning outcomes.
SELECT
    status,
    COUNT(*) AS lines,
    SUM(amount) AS amount,
    COUNT(*) FILTER (WHERE customer_id IS NULL) AS lines_without_customer
FROM lines
GROUP BY status
ORDER BY lines DESC;
