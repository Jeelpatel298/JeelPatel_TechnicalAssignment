# Sales & Inventory

A Flask and MySQL application for managing customers, products, sales orders, and stock at a small trading company.

## Run locally

Use Python 3.9 or later, MySQL 8.4 with InnoDB, and a current browser with JavaScript enabled. Verification used Python 3.9.6, MySQL 8.4.11, and Chromium.

1. From a MySQL administrative session, create the database and a local application account. Choose your own password and enter the same value in `.env`.

   ```sql
   CREATE DATABASE sales_inventory CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
   CREATE USER 'inventory_app'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_YOUR_PASSWORD';
   GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, REFERENCES
   ON sales_inventory.* TO 'inventory_app'@'127.0.0.1';
   ```

2. From the repository root, install dependencies and prepare the environment.

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   cp .env.example .env
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

   On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1` and copy the file with `Copy-Item .env.example .env`. In `.env`, set `DB_PASSWORD` and paste the generated value into `SECRET_KEY`. Update the MySQL host or port if your installation uses a different address.

3. Create the tables, add sample data, and start the app.

   ```sh
   flask --app inventory init-db
   flask --app inventory seed
   flask --app inventory run
   ```

   The seed command prompts for each demo password and inserts sample customers, products, and opening-stock movements. Run it once on an empty database. Visit <http://127.0.0.1:5000> and sign in with a password you set.

| Sample email | Role | Access |
| --- | --- | --- |
| admin@example.test | Admin | Edit the catalog, adjust stock, manage all orders, view reports, and import CSVs |
| sales@example.test | Sales User | Browse active customers and products and manage their own orders |
| sales2@example.test | Sales User | A separate account for verifying order isolation |

## Basic workflow

1. Sign in as a Sales User. Create a draft for Aster Retail with two keyboards, three mice, and a 10% discount. Expected subtotal, discount and total are ₹4,500.00, ₹450.00 and ₹4,050.00.
2. Confirm the draft. Keyboard stock decreases from 20 to 18 and mouse stock from 50 to 47. After cancelling the confirmed order, stock returns to 20 and 50.
3. While a confirmed order exists, sign in as Admin and run the reports. The customer summary uses the net order total and the product summary uses gross item amounts.
4. In CSV import, try [the invalid file](samples/products-invalid.csv), followed by [the valid file](samples/products-valid.csv). The first upload shows row errors. The second adds two products and their positive opening-stock movements.

## Database and correctness

- Customers and users each relate to many orders. An order relates to products through its order items, with a unique order/product pair. Stock movements link to a product and the acting user, and can link to an order. Foreign keys protect historical references. Referenced customer or product records can be deactivated.
- Money uses MySQL `DECIMAL` and Python `Decimal`. Subtotal is the sum of line amounts. The discount is rounded to the nearest cent using half-up rounding, then subtracted. Existing draft items retain their captured rates during quantity edits. Newly added products use the current price. Browser previews use integer cents.
- Confirmation and cancellation lock the order row first. They then lock relevant product rows in ascending primary-key order. The locks serialize status changes for the same order and competing changes to the same stock. Writes to order state, product balances, and movement records commit together. Insufficient stock rolls back every write. A repeated action targeting the current status returns that order with zero additional movement.
- Adjustments lock the product row before checking its new balance. Positive opening balances from creation or CSV import get an Opening movement. Zero opening balances create no stock change. CSV validation and insertion run in a transaction, and a unique product code constraint catches a conflicting insert.
- Sales reports read only Confirmed orders. The customer report uses a left join with status and date filters inside the join, so customers without qualifying orders show zero. It aggregates orders directly, avoiding order-item duplication.
- Routes enforce role and ownership on the server. Flask's signed session cookie stores the user ID and CSRF token. Passwords are stored as salted PBKDF2-SHA256 hashes, and mutating calls require the current CSRF token.

See the [MySQL locking reads reference](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html) for InnoDB locking semantics.

## Run the tests

Run just the calculation and debugging tests without MySQL.

```sh
python -m pytest -q tests/test_pricing.py
```

Run the full suite against a local or disposable MySQL test server. Set `TEST_DB_USER` and `TEST_DB_PASSWORD` for an account permitted to create and drop the temporary test schema and run the schema's DDL and DML. The suite generates a unique `inventory_test_` database and removes it at teardown. `TEST_DB_HOST` and `TEST_DB_PORT` default to `127.0.0.1` and `3306`. The application's configured database is independent of integration testing.

```sh
export TEST_DB_USER=your_local_test_admin
read -rs TEST_DB_PASSWORD
export TEST_DB_PASSWORD
python -m pytest -q
```

## Files

| File or directory | Contents |
| --- | --- |
| [inventory/](inventory/) | Flask app, routes, catalog and order services, and browser interface |
| [sql/schema.sql](sql/schema.sql) | Six-table schema, constraints, indexes, and foreign keys |
| [sql/reports.sql](sql/reports.sql) | Five standalone SQL reporting queries |
| [API.md](API.md) | Cookie and CSRF workflow, request examples, and response shapes |
| [DEBUGGING.md](DEBUGGING.md) | Fault analysis, corrected implementation, and regression tests |
| [AI_USAGE.md](AI_USAGE.md) | AI usage, review, and corrections |
| [tests/](tests/) | Pricing and real-MySQL integration tests |

Run the standalone SQL with `mysql -h 127.0.0.1 -u inventory_app -p sales_inventory < sql/reports.sql`. Change `@stock_threshold` in that file to supply a different threshold.

## Scope and limitations

- The app uses INR, one stock location, whole units, and UTC for default order dates and movement timestamps. Taxes, delivery, purchasing, and payments are outside scope.
- Drafts hold up to 100 unique products. Deactivating a record blocks its selection in new or updated drafts. Previously saved orders remain available, and their saved drafts can still be confirmed or cancelled.
- The customer sales report accepts a date range. The product sales summary covers all confirmed orders. The order list and report screens are sized for a small local data set.
- User provisioning is through the seed command for local review. The Flask development server and default cookie configuration are for loopback HTTP. A hosted deployment would need a production WSGI server, HTTPS, secure cookies, and login rate limiting.
