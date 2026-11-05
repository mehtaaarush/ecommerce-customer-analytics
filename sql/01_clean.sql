-- Classify every raw line exactly once, so the cleaning funnel adds up to the raw row count.
-- Order matters: a repeated cancellation counts as a duplicate, a cancelled postage line as non-product.
CREATE OR REPLACE TABLE lines AS
WITH numbered AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY invoice, stock_code, description, quantity, invoice_date, price, customer_id, country
        ) AS copy_number
    FROM raw_lines
),
classified AS (
    SELECT
        invoice,
        stock_code,
        description,
        quantity,
        invoice_date,
        price,
        customer_id,
        country,
        quantity * price AS amount,
        CASE
            WHEN copy_number > 1 THEN 'duplicate'
            -- merchandise codes start with five digits (85123A) or belong to the gift-shop range (DCGS...);
            -- postage, carriage, fees, manual adjustments, discounts, samples, tests and vouchers do not
            WHEN NOT regexp_matches(stock_code, '^([0-9]{5}|DCGS)') THEN 'non-product'
            WHEN invoice LIKE 'C%' THEN 'cancellation'
            WHEN quantity <= 0 OR price <= 0 THEN 'invalid quantity or price'
            ELSE 'sale'
        END AS status
    FROM numbered
),
typical_price AS (
    SELECT stock_code, median(price) AS median_price
    FROM classified
    WHERE status = 'sale'
    GROUP BY stock_code
)
SELECT
    c.invoice,
    c.stock_code,
    c.description,
    c.quantity,
    c.invoice_date,
    c.price,
    c.customer_id,
    c.country,
    c.amount,
    CASE
        WHEN c.status = 'sale' AND c.price > $price_error_factor * t.median_price THEN 'price error'
        ELSE c.status
    END AS status
FROM classified AS c
LEFT JOIN typical_price AS t USING (stock_code);
