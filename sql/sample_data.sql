-- Run once after schema.sql on an empty catalog.
-- Product balances start at zero so loading this file needs no stock movement or user.
INSERT INTO customers (name, email, mobile, city) VALUES
  ('Aster Retail', 'hello@aster.example', '+91 90000 00001', 'Ahmedabad'),
  ('Bluebird Office', 'hello@bluebird.example', '+91 90000 00002', 'Surat'),
  ('Cedar Supply', 'hello@cedar.example', '+91 90000 00003', 'Vadodara');

INSERT INTO products (code, name, category, price) VALUES
  ('PRD-001', 'Keyboard', 'Accessories', 1500.00),
  ('PRD-002', 'Mouse', 'Accessories', 500.00),
  ('PRD-003', 'USB-C Hub', 'Connectivity', 1899.00),
  ('PRD-004', 'Monitor Riser', 'Workspace', 2400.00);
