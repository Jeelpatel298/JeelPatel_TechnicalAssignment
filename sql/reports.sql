-- 1. Top three customers by confirmed sales after discount.
SELECT c.id, c.name, SUM(o.grand_total) AS sales_total
FROM customers c JOIN orders o ON o.customer_id = c.id
WHERE o.status = 'Confirmed'
GROUP BY c.id, c.name
ORDER BY sales_total DESC, c.id
LIMIT 3;

-- 2. Top three products by quantity sold in confirmed orders.
SELECT p.id, p.code, p.name, SUM(i.quantity) AS quantity_sold
FROM products p JOIN order_items i ON i.product_id = p.id
JOIN orders o ON o.id = i.order_id
WHERE o.status = 'Confirmed'
GROUP BY p.id, p.code, p.name
ORDER BY quantity_sold DESC, p.id
LIMIT 3;

-- 3. Customers who have never placed any order.
SELECT c.id, c.name
FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)
ORDER BY c.name, c.id;

-- 4. Confirmed sales by calendar year and month.
SELECT YEAR(order_date) AS sales_year, MONTH(order_date) AS sales_month,
       SUM(grand_total) AS sales_total
FROM orders
WHERE status = 'Confirmed'
GROUP BY YEAR(order_date), MONTH(order_date)
ORDER BY sales_year, sales_month;

-- 5. Products below a supplied threshold. Change this value as needed.
SET @stock_threshold = 10;
SELECT id, code, name, stock
FROM products
WHERE stock < @stock_threshold
ORDER BY stock, code;
