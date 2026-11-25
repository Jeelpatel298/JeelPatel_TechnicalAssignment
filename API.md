# REST API

The API returns JSON and uses a signed session cookie. First fetch the CSRF token, then sign in with the same cookie jar. Sign-in replaces the session, so fetch the token again before sending any further write requests. To sign out, send `POST /api/logout` with that token and the cookie.

The examples use a fresh seeded database and a local server. Use the password selected during seeding. The file passed to `curl -c` holds a live session and should stay local.

```sh
base=http://127.0.0.1:5000
jar=$(mktemp)
token() {
  curl -fsS -b "$jar" -c "$jar" "$base/api/session" |
    python -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])'
}
csrf=$(token)
read -rs demo_password
printf '%s' "$demo_password" |
  python -c 'import json,sys; print(json.dumps({"email": "sales@example.test", "password": sys.stdin.read()}))' |
  curl -fsS -b "$jar" -c "$jar" -H "X-CSRF-Token: $csrf" \
    -H 'Content-Type: application/json' --data-binary @- "$base/api/login"
unset demo_password
csrf=$(token)
```

Successful login returns `{"ok":true}`.

## Find active products

```sh
curl -fsS -b "$jar" "$base/api/products?q=keyboard&page=1&per_page=10"
```

```json
{
  "items": [{"id": 1, "code": "PRD-001", "name": "Keyboard", "category": "Accessories", "price": "1500.00", "stock": 20, "active": 1}],
  "page": 1,
  "per_page": 10,
  "total": 1
}
```

## Create and retrieve a draft

Get IDs from `GET /api/catalog/customers?status=Active` and `GET /api/products`. Adjust the example IDs for your database.

```sh
curl -fsS -b "$jar" -H "X-CSRF-Token: $csrf" -H 'Content-Type: application/json' \
  --data '{"customer_id":1,"order_date":"2026-11-24","discount_pct":"10.00","items":[{"product_id":1,"quantity":2},{"product_id":2,"quantity":3}]}' \
  "$base/api/orders"
```

`201 Created` with a `Location` header. Example response excerpt follows.

```json
{
  "id": 1,
  "number": "SO-2026-000001",
  "customer_id": 1,
  "order_date": "2026-11-24",
  "status": "Draft",
  "discount_pct": "10.00",
  "subtotal": "4500.00",
  "discount_amount": "450.00",
  "grand_total": "4050.00",
  "items": [
    {"product_id": 1, "quantity": 2, "rate": "1500.00", "amount": "3000.00"},
    {"product_id": 2, "quantity": 3, "rate": "500.00", "amount": "1500.00"}
  ]
}
```

```sh
curl -fsS -b "$jar" "$base/api/orders/1"
```

`GET /api/orders/1` returns the same detail shape with `200 OK`. Send the same request body to `PUT /api/orders/1` to replace a draft's editable fields. `GET /api/orders` lists visible orders.

## Confirm and cancel

```sh
curl -fsS -b "$jar" -H "X-CSRF-Token: $csrf" -X POST "$base/api/orders/1/confirm"
curl -fsS -b "$jar" -H "X-CSRF-Token: $csrf" -X POST "$base/api/orders/1/cancel"
```

Successful actions return `200 OK` and the updated order, with `"status":"Confirmed"` or `"status":"Cancelled"`. A conflicting action or shortage returns `409 Conflict`.

```json
{"error":"Insufficient stock for PRD-003. Available: 4, required: 5."}
```

## Other endpoints

| Method and path | Behavior |
| --- | --- |
| GET /api/catalog/customers or /api/catalog/products | Search with `q`, paginate with `page` and `per_page`. Products accept `category`. Admin can filter with `status=Active` or `status=Inactive`. |
| GET /api/catalog/{customers or products}/{id} | Retrieve one visible catalog record, including price and stock for a product. |
| POST /api/catalog/{customers or products} | Admin creates a record. Customer fields are `name`, `email`, `mobile`, `city`, and `status`. Product fields are `code`, `name`, `category`, `price`, `status`, and optional opening `stock`. |
| PUT or DELETE /api/catalog/{customers or products}/{id} | Admin edits or deletes a record. Use `status: "Inactive"` to deactivate. Successful deletion returns 204. |
| POST /api/products/{id}/adjust | Admin sends `{"change":2,"reason":"Physical stock count"}`. |
| POST /api/products/import | Admin uploads a multipart `file`. A successful import returns `201` and `{"imported":2}`. Validation errors include an `errors` list of row numbers and reasons. |
| GET /api/reports | Admin retrieves `customers`, `products`, `low_stock`, and `movements`. Optional parameters are `start`, `end`, and `threshold`. |

Dates use ISO format and money values are returned as strings. Common error responses use `{"error":"message"}`. Invalid inputs return 400, unauthenticated protected requests return 401, role and CSRF failures return 403, missing records and orders outside a Sales User’s access return 404, and business conflicts return 409.

```sh
curl -fsS -b "$jar" -H "X-CSRF-Token: $csrf" -X POST "$base/api/logout"
rm "$jar"
```
