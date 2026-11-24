CREATE TABLE IF NOT EXISTS users (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(254) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('admin','sales') NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS customers (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(254) NOT NULL,
  mobile VARCHAR(30) NOT NULL,
  city VARCHAR(100) NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE CHECK (active IN (0,1)),
  INDEX (active, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS products (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(40) NOT NULL COLLATE utf8mb4_0900_as_ci UNIQUE,
  name VARCHAR(120) NOT NULL,
  category VARCHAR(80) NOT NULL,
  price DECIMAL(12,2) NOT NULL CHECK (price >= 0),
  stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
  active BOOLEAN NOT NULL DEFAULT TRUE CHECK (active IN (0,1)),
  INDEX (active, category, name),
  INDEX (stock)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS orders (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  number VARCHAR(35) NOT NULL UNIQUE,
  customer_id INT UNSIGNED NOT NULL,
  order_date DATE NOT NULL,
  status ENUM('Draft','Confirmed','Cancelled') NOT NULL DEFAULT 'Draft',
  discount_pct DECIMAL(4,2) NOT NULL CHECK (discount_pct BETWEEN 0 AND 20),
  subtotal DECIMAL(22,2) NOT NULL CHECK (subtotal >= 0),
  discount_amount DECIMAL(22,2) NOT NULL CHECK (discount_amount BETWEEN 0 AND subtotal),
  grand_total DECIMAL(22,2) NOT NULL CHECK (grand_total = subtotal - discount_amount),
  created_by INT UNSIGNED NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(id),
  FOREIGN KEY (created_by) REFERENCES users(id),
  INDEX (status, order_date),
  INDEX (customer_id, status, order_date),
  INDEX (created_by, order_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS order_items (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id INT UNSIGNED NOT NULL,
  product_id INT UNSIGNED NOT NULL,
  quantity INT NOT NULL CHECK (quantity > 0),
  rate DECIMAL(12,2) NOT NULL CHECK (rate >= 0),
  amount DECIMAL(22,2) NOT NULL CHECK (amount = quantity * rate),
  FOREIGN KEY (order_id) REFERENCES orders(id),
  FOREIGN KEY (product_id) REFERENCES products(id),
  UNIQUE (order_id, product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS stock_movements (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  product_id INT UNSIGNED NOT NULL,
  movement_type ENUM('Opening','Adjustment','Sale','Return') NOT NULL,
  quantity_change INT NOT NULL CHECK (quantity_change <> 0),
  order_id INT UNSIGNED,
  reason VARCHAR(255) NOT NULL,
  created_by INT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (product_id) REFERENCES products(id),
  FOREIGN KEY (order_id) REFERENCES orders(id),
  FOREIGN KEY (created_by) REFERENCES users(id),
  UNIQUE (order_id, product_id, movement_type),
  INDEX (product_id, created_at),
  INDEX (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
