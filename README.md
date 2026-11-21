# ShopSphere – multi-vendor marketplace (Django + HTML/CSS/JS)

Customers shop many independent stores in **one cart**. Vendors run their own dashboard. The marketplace
takes a **commission** on each sale and pays vendors out. Backend: Django (pure, no DRF). Frontend: server-rendered
templates + vanilla JS calling a JSON API.

## Run it (Windows / macOS / Linux)

```bash
unzip shopsphere.zip && cd shopsphere
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations accounts vendors catalog orders   # first time only (custom user model)
python manage.py migrate
python manage.py seed_demo                                         # demo data (optional)
python manage.py runserver
```
Open http://127.0.0.1:8000

Demo logins (after `seed_demo`): `admin / admin12345` (admin panel at /admin/), `vendor1..3 / demo12345`,
`customer / demo12345`. Coupons: `WELCOME10` (10%), `SAVE5` ($5 off $30+). Test cards: any 16 digits succeeds,
`4000000000000002` is declined.

Other commands: `python manage.py test` (runs tests), `python manage.py createsuperuser`,
`python manage.py collectstatic`, Docker: `docker build -t shopsphere . && docker run -p 8000:8000 shopsphere`.
Production: set `DEBUG=0`, `SECRET_KEY`, `ALLOWED_HOSTS`, PostgreSQL vars (see `.env.example`) and run behind gunicorn (`gunicorn config.wsgi`).

## Features
Accounts (email-or-username login, rate-limited, password reset, profile, address book, notifications) ·
Vendors (apply → admin approval, storefront, product CRUD, variants, gallery, order fulfilment with tracking, returns, earnings, payouts, analytics) ·
Catalog (categories tree, search + live suggestions, filters, sort, pagination, reviews with verified-purchase, wishlist, recently viewed, related items, discounts) ·
Cart (guest + user, merges on login, stock checks, coupons, free-shipping progress) ·
Checkout (saved addresses, shipping, tax, card/COD, atomic stock locking, multi-vendor order split) ·
Orders (timeline, cancel + auto-restock/refund, per-item returns, invoice) ·
Admin (approve vendors, commissions, payouts, coupons, orders) ·
2026 extras: PWA (manifest + service worker + offline page), dark mode, SEO (meta, JSON-LD, sitemap.xml, robots.txt),
accessibility (skip link, ARIA, reduced motion), security headers/CSRF/HSTS in production, health check, Docker.

## Money rules (edit in `config/settings.py`)
Tax 8% · flat shipping $5, free ≥ $50 · default commission 10% (per-vendor override in admin) · return window 14 days ·
min payout $20. Vendor earnings count only when an item is **delivered**.

## Pages (HTML)
| URL | Purpose |
|---|---|
| `/` | Home: hero, categories, featured, new, top rated, recently viewed |
| `/shop/` , `/shop/c/<category>/` | Product listing with search/filter/sort (`?q=&min_price=&max_price=&rating=&in_stock=1&on_sale=1&sort=`) |
| `/shop/p/<slug>/` | Product page (gallery, variants, reviews, related, JSON-LD) |
| `/shop/p/<slug>/review/` POST | Add/update review |
| `/shop/wishlist/` | My wishlist |
| `/store/<slug>/` | Public vendor storefront |
| `/cart/` | Cart (rendered by JS from API) |
| `/checkout/` | Address, payment method, place order (login required) |
| `/pay/<order_no>/` | Demo card gateway page |
| `/orders/` , `/orders/<no>/` | Order history / detail with tracking timeline |
| `/orders/<no>/invoice/` | Printable invoice |
| `/orders/<no>/cancel/` POST | Cancel whole order (restocks, refunds) |
| `/orders/item/<id>/return/` POST | Request return for delivered item |
| `/payments/webhook/` POST | Gateway webhook (HMAC `X-Signature`), marks order paid |
| `/accounts/register/ login/ logout/(POST)` | Auth |
| `/accounts/profile/ addresses/ notifications/` | Account area (+ `addresses/<id>/delete/`, `addresses/<id>/default/`, `notifications/read/` POST) |
| `/accounts/password-reset/ …` | Password reset flow (4 URLs) |
| `/about/ /privacy/ /terms/ /shipping-returns/ /contact/ /offline/` | Static pages |
| `/robots.txt /sitemap.xml /manifest.webmanifest /sw.js /healthz/` | SEO / PWA / health |
| `/admin/` | Django admin |

## Vendor portal (`/vendor/…`, approved vendors only)
`apply/` become a seller · `` dashboard · `products/` list · `products/new/` · `products/<id>/edit/` · `products/<id>/delete/` POST ·
`products/<id>/variants/add/` POST · `variants/<id>/delete/` POST · `products/<id>/images/add/` POST · `images/<id>/delete/` POST ·
`orders/` · `orders/item/<id>/update/` POST (process → ship+tracking → deliver, or cancel) · `returns/` · `returns/<id>/resolve/` POST ·
`payouts/` · `payouts/request/` POST · `settings/`

## JSON API (`/api/…`, session auth, send `X-CSRFToken` on POST)
| Endpoint | Method | Does |
|---|---|---|
| `/api/health/` | GET | Liveness |
| `/api/categories/` | GET | All categories |
| `/api/products/` | GET | Search/filter/paginate (`q, category, min_price, max_price, rating, in_stock, on_sale, sort, page, page_size`) |
| `/api/products/<slug>/` | GET | Product detail with variants/images |
| `/api/suggest/?q=` | GET | Search autocomplete |
| `/api/cart/` | GET | Cart with totals |
| `/api/cart/add/` | POST | `{product_id, variant_id?, quantity}` |
| `/api/cart/update/` | POST | `{item_id, quantity}` (0 removes) |
| `/api/cart/remove/` | POST | `{item_id}` |
| `/api/cart/clear/` | POST | Empty cart |
| `/api/cart/coupon/` | POST | `{code}` apply; empty code removes |
| `/api/wishlist/` | GET | My wishlist (login) |
| `/api/wishlist/toggle/` | POST | `{product_id}` (login) |
| `/api/orders/` | GET | My orders (login) |
| `/api/notifications/` , `/api/notifications/read/` | GET / POST | List / mark read (login) |
| `/api/vendor/stats/` | GET | 30-day revenue + balance (vendors) |

## Not included / next steps (be aware)
Real payment gateway (mock + webhook skeleton only – wire Stripe/Razorpay in `orders/services.py`), real shipping-rate/tax
APIs, guest checkout, email verification, PostgreSQL full-text/Elasticsearch search, S3 media storage, multi-currency/i18n, Celery for async email.
