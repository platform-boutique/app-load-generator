"""Form payloads, field names as in the frontend templates (cart.html, accounts, reviews)."""

from __future__ import annotations

from datetime import date

OK_CARD = "4111111111111111"
DECLINED_CARD = "4000000000000002"


def checkout_form(idempotency_key: str, card: str, today: date | None = None) -> dict[str, str]:
    year = (today or date.today()).year + 2
    return {
        "idempotency_key": idempotency_key,
        "email": "loadgen@example.com",
        "street_address": "1 Market Street",
        "zip_code": "94043",
        "city": "Springfield",
        "state": "CA",
        "country": "United States",
        "credit_card_number": card,
        "credit_card_expiration_month": "1",
        "credit_card_expiration_year": str(year),
        "credit_card_cvv": "672",
    }


def add_to_cart_form(product_id: str, quantity: int = 1) -> dict[str, str]:
    return {"product_id": product_id, "quantity": str(quantity)}


def register_form(name: str, email: str, password: str) -> dict[str, str]:
    return {"name": name, "email": email, "password": password}


def login_form(email: str, password: str) -> dict[str, str]:
    return {"email": email, "password": password}


def review_form(author: str, rating: int, comment: str) -> dict[str, str]:
    return {"author_name": author, "rating": str(rating), "comment": comment}
