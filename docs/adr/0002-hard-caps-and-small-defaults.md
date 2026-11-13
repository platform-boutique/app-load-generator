# 2. Hard caps for orders and reviews, small defaults

Status: accepted (reconstructed from the code and the earlier README).

## Context

The generator writes real demo data: orders take stock, reviews change star averages, accounts accumulate.

## Decision

Hard per-run caps (`MAX_ORDERS`, default 30; `MAX_REVIEWS`, default 10; `0` switches the action off), polite defaults (5 users, spawn rate 1, think time 1 to 3 s) and a product choice that only buys plainly in-stock products.

## Consequences

- A run cannot drain the stock of a product.
- Cleanup is only `docker compose down -v`; nothing here deletes the data.
- The compose profile uses even smaller defaults (3 users, 5 orders, 3 reviews).
