# API (journeys)

There is no server. The tool is a client of the frontend's HTML routes; its interface is the environment ([configuration](configuration.md)), the exit code and the printed summary.

Exit code: 0 when the failure ratio is within `FAIL_RATIO`; 1 when it is above, or when no request was made; 2 for a bad configuration.

## Journeys

Each simulated user is one visitor with its own cookie jar. Tasks are picked by weight; a step that fails ends that
journey (no cascade of follow-up failures).

| Journey (`JOURNEYS` name) | Weight | What it does | What counts as a failure |
|---|---|---|---|
| `browse` | 10 | home, a random department, a search (a tag seen on product pages; 1 in 5 is a nonsense word), a sort, page 2 of the catalog | not 200, brand `Everly` missing, a page without product cards, `Nothing found` missing for the nonsense search |
| `product_view` | 8 | product page, then one of its recommendations | not 200, add-to-cart form or `Customer reviews` missing, **no recommendations block** |
| `add_to_cart` | 4 | pick an in-stock product, add it, cart page, empty the cart, check the cart is empty | add is not 302 to `/cart`, cart lacks the product or the `idempotency_key`, cart not empty afterwards |
| `checkout_success` | 3 | add, cart, checkout with `4111111111111111` using the **idempotency key read from the rendered cart page** | not 200, `Your order is complete` or the confirmation id missing. Skipped once `MAX_ORDERS` is used up |
| `checkout_declined` | 2 | add, cart, checkout with `4000000000000002`, empty the cart | not the clean 422 page (`We could not process that`, `declined`, link back to the cart), or the order-complete page appears |
| `out_of_stock` | 1 | add a sold-out product (default `volleyball-153`, stock 0 in the catalog seed) | not 422 with `out of stock` |
| `review` | 1 | post a review ("loadgen bot xxxxxx", random 1 to 5 stars) on a random product | not 303 back to the product, `your review has been posted` missing. Stops after `MAX_REVIEWS` |
| `account` | 1 | register (once per simulated user) or sign in, one wrong-password attempt (once per user), `/account`, an order if the budget allows, then order history, order page, **mailbox poll for the confirmation mail** (up to 20 x 1 s) and the mail page (sandboxed iframe), logout | wrong status or marker anywhere, `Wrong email or password` missing on the 422, the order missing in the history, the mail never arriving |

Every response is also checked for leaked internals (`rpc error`, Go stack traces, password hashes). Redirects are
never followed automatically; a journey follows only the ones it expects, and only to the same host. Static assets
(images, CSS, JS) are not fetched, only the HTML pages.

Product choice for carts: the generator only buys products whose page says plainly `In stock` (not `Only N left`,
not sold out), so a run does not take the last units of anything. Failed requests are named with a short constant
message, so the summary groups them by cause.

Cookies: the frontend marks its cookies `Secure`; `python-requests` would not send them back over `http://`, which
would turn every request into a new visitor. The client clears the flag on received cookies (see `client.py`).
