"""Shared constants for the shipping_pw package."""

BASE_URL = "http://127.0.0.1:7770"
CART_URL = f"{BASE_URL}/checkout/cart/"
CHECKOUT_URL = f"{BASE_URL}/checkout/"
WISHLIST_URL = f"{BASE_URL}/wishlist/"
ACCOUNT_EDIT_URL = f"{BASE_URL}/customer/account/edit/"
ADDRESS_BOOK_URL = f"{BASE_URL}/customer/address/"
ORDER_HISTORY_URL = f"{BASE_URL}/sales/order/history/"
LOGIN_URL = f"{BASE_URL}/customer/account/login/"

# Luma admin panel — separate Magento backend on port 7780.
ADMIN_BASE_URL = "http://127.0.0.1:7780"
ADMIN_LOGIN_URL = f"{ADMIN_BASE_URL}/admin"
