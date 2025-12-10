# PTE

## How to add a new API

Go to `/api`, duplicate the template and follow the instructions at the top of the file
Do this in a new branch, and submit a PR when you are done with a website

## Shopping search sanity test

Use `search_test.py` to call the `api.shopping.search_products` endpoint with any search term:

```bash
python search_test.py "hoodie" --username customer@example.com --password secret
```

If you omit the arguments, the script prompts for input. It authenticates via `customer_login` first (required by Magento) and then prints the search results as formatted JSON so you can quickly verify what the storefront returns for that query.

## Shopping cart sanity test

Use `add_to_cart_test.py` to spin up a customer cart and add a SKU through `api.shopping.add_to_cart`:

```bash
python add_to_cart_test.py 24-MB01 --qty 1
```

If you omit the SKU, the script prompts interactively. Provide `--quote-id` to reuse an existing cart; otherwise it creates one for you, clears any existing line items, adds the SKU, and then fetches the cart contents to ensure the product actually landed in the cart (fails loudly if it did not).
