import json
project_templates = {
    "Ruby on Rails": {
        "id": "rails",
        "description": "Includes an MVC structure, Gemfile, Rakefile, along with many others, to help you get started"
    },
    "Spring": {
        "id": "spring",
        "description": "Includes an MVC structure, mvnw and pom.xml to help you get started"
    },
    "NodeJS Express": {
        "id": "express",
        "description": "Includes an MVC structure to help you get started"
    },
    "iOS (Swift)": {
        "id": "iosswift",
        "description": "A ready-to-go template for use with iOS Swift apps"
    },
    ".NET Core": {
        "id": "dotnetcore",
        "description": "A .NET Core console application template, customizable for any .NET Core project"
    },
    "Android": {
        "id": "android",
        "description": "A ready-to-go template for use with Android apps"
    },
    "Go Micro": {
        "id": "gomicro",
        "description": "Go Micro is a framework for micro service development"
    },
    "Pages/Bridgetown": {
        "id": "bridgetown",
        "description": "Everything you need to create a GitLab Pages site using Bridgetown"
    },
    "Pages/Gatsby": {
        "id": "gatsby",
        "description": "Everything you need to create a GitLab Pages site using Gatsby"
    },
    "Pages/Hugo": {
        "id": "hugo",
        "description": "Everything you need to create a GitLab Pages site using Hugo"
    },
    "Pages/Pelican": {
        "id": "pelican",
        "description": "Everything you need to create a GitLab Pages site using Pelican"
    },
    "Pages/Jekyll": {
        "id": "jekyll",
        "description": "Everything you need to create a GitLab Pages site using Jekyll"
    },
    "Pages/Plain HTML": {
        "id": "plainhtml",
        "description": "Everything you need to create a GitLab Pages site using plain HTML"
    },
    "Pages/GitBook": {
        "id": "gitbook",
        "description": "Everything you need to create a GitLab Pages site using GitBook"
    },
    "Pages/Hexo": {
        "id": "hexo",
        "description": "Everything you need to create a GitLab Pages site using Hexo"
    },
    "Pages/Middleman": {
        "id": "middleman",
        "description": "Everything you need to create a GitLab Pages site using Middleman"
    },
    "Gitpod/Spring Petclinic": {
        "id": "gitpod_spring_petclinic",
        "description": "A Gitpod configured Webapplication in Spring and Java"
    },
    "Netlify/Hugo": {
        "id": "nfhugo",
        "description": "A Hugo site that uses Netlify for CI/CD instead of GitLab, but still with all the other great GitLab features"
    },
    "Netlify/Jekyll": {
        "id": "nfjekyll",
        "description": "A Jekyll site that uses Netlify for CI/CD instead of GitLab, but still with all the other great GitLab features"
    },
    "Netlify/Plain HTML": {
        "id": "nfplainhtml",
        "description": "A plain HTML site that uses Netlify for CI/CD instead of GitLab, but still with all the other great GitLab features"
    },
    "Netlify/GitBook": {
        "id": "nfgitbook",
        "description": "A GitBook site that uses Netlify for CI/CD instead of GitLab, but still with all the other great GitLab features"
    },
    "Netlify/Hexo": {
        "id": "nfhexo",
        "description": "A Hexo site that uses Netlify for CI/CD instead of GitLab, but still with all the other great GitLab features"
    },
    "SalesforceDX": {
        "id": "salesforcedx",
        "description": "A project boilerplate for Salesforce App development with Salesforce Developer tools"
    },
    "Serverless Framework/JS": {
        "id": "serverless_framework",
        "description": "A basic page and serverless function that uses AWS Lambda, AWS API Gateway, and GitLab Pages"
    },
    "Tencent Serverless Framework/NextjsSSR": {
        "id": "tencent_serverless_framework",
        "description": "A project boilerplate for Tencent Serverless Framework that uses Next.js SSR"
    },
    "Jsonnet for Dynamic Child Pipelines": {
        "id": "jsonnet",
        "description": "An example showing how to use Jsonnet with GitLab dynamic child pipelines"
    },
    "GitLab Cluster Management": {
        "id": "cluster_management",
        "description": "An example project for managing Kubernetes clusters integrated with GitLab"
    },
    "Kotlin Native Linux": {
        "id": "kotlin_native_linux",
        "description": "A basic template for developing Linux programs using Kotlin Native"
    },
    "TYPO3 Distribution": {
        "id": "typo3_distribution",
        "description": "A template for starting a new TYPO3 project"
    }
}


GITLAB_HINTS = f"""
GitLab project `{{id}}` path parameter has exactly two directly usable forms:

- a numeric project ID, for example `42`
- a namespace-qualified project path of the form `namespace/project`, for example `byteblaze/a11yproject`

A plain project name such as `a11yproject` is NOT a valid directly usable `{{id}}` value.

Decision rule:
- If the task provides a numeric ID, use it directly.
- If the task provides a namespace-qualified path matching `namespace/project`, use it directly.
- Otherwise, you MUST first resolve the project using a lookup endpoint such as `GET /projects?search=...` before calling endpoints that require `/projects/{{id}}/...`.

When using `GET /projects?search=...`:
- The `search` value must be the project name only (e.g. `design`), NOT a `namespace/project` path (e.g. `primer/design`).
- If you already have a `namespace/project` path, that IS the valid `{{id}}` — use it directly and skip the search step.

Do not assume that a single project name can be used directly as `{{id}}`.
Do not assume that a parameter named `{{id}}` can be guessed or partially matched.

GitLab user `{{id}}` path parameter has exactly two directly usable forms:

- a numeric user ID, for example `2330`
- a username, for example `byteblaze`

You do NOT know your own user ID or username — if the task requires acting on "my" account, you MUST first resolve your user info using a lookup endpoint before calling endpoints any form of {{id}} or {{username}} parameter.
Do NOT pass string aliases like 'self', 'me', or 'current_user' for parameters that require an ID/username — add a prior step to look up the real value instead.
You do NOT know the user IDs or usernames of any other users — if the task requires acting on another user, you MUST first resolve that user's info using a lookup endpoint before calling endpoints with any form of {{id}} or {{username}} parameter.

When determining default_branch for a repository, do NOT assume it is always 'main' or 'master'. Look up the default branch instead.

Adding collaborators:
Use POST /projects/{id}/members to add a user directly and immediately — the user appears in project_members at once. POST /projects/{id}/invitations sends an email invitation that requires the recipient to accept; the user will NOT appear in project_members until they do. Always prefer POST /projects/{id}/members when the task is to add a collaborator or member.

Repository disambiguation:
When a task names a repository without specifying an owner and multiple matches exist — including a fork owned by byteblaze — always prefer the original non-byteblaze repo (i.e. the one not in the byteblaze namespace).

Pagination:
All GitLab list endpoints return at most 20 items by default (per_page=20). Results beyond the first 20 are silently omitted unless you request more.
- Always set per_page=100 (the maximum) on any list endpoint when the task requires finding ALL items, ranking (e.g. "most", "least", "top N"), counting, or comparing across the full result set. Missing a page means missing data and producing a wrong answer.
- If a task asks for the top N items by some field (e.g. stars, commits), fetch with per_page=100 so that sorting and slicing happen over the complete list, not just the first page.
- Commit authors may appear under multiple name or email variants (e.g. "Steve Woodson" and "Steven Woodson"). When counting commits by a person, sum all contributor entries whose name or email plausibly refers to the same individual — do not count only the entry with the largest commit count.
- When filtering commits by date, always use full ISO 8601 timestamps with explicit time and timezone: `since=2023-02-06T00:00:00Z&until=2023-02-07T00:00:00Z`. Using a bare date like `until=2023-02-06` is interpreted as midnight UTC and will exclude all commits made later that day.
- This GitLab instance has more than 100 projects. For ranking tasks (top N by star count, most commits, etc.) that fetch all projects, you MUST fetch both page 1 AND page 2 with per_page=100 to cover the full project list. Use two parallel steps with page=1 and page=2, combine the results, then sort and slice client-side.
- When searching for a merge request by topic or description and the exact title is unknown, do NOT use the `search` parameter — it requires an exact title match and will return empty if phrasing differs. Instead fetch all MRs with state=all and no search filter, then identify the relevant MR from the full list in the answer generation step.

For Project Templates. Use this json schema to search through available built-in templates. Otherwise, leave template_name blank.

{json.dumps(project_templates, indent=2)}

"""

REDDIT_HINTS = f"""
When looking up a specific post by title or keyword, use GET /search rather than GET /user_posts.
/user_posts is paginated and may not return all of a user's posts, so it can miss the target post.
/search performs a full-text search across all posts and reliably surfaces the relevant result.

GET /search ranks by keyword frequency across title and body, not by relevance or exact match — the first result is not necessarily the best match.
Always inspect the full result list and select the correct post by matching on its title, author, or subreddit rather than assuming rank order reflects intent.

Forum names are case-sensitive and must match exactly. When a forum name is not explicitly given or you are unsure of the exact casing, call GET /list_forums first to retrieve the canonical name before using it in any other endpoint. The user's phrasing may not match the canonical name exactly — apply best-guess fuzzy matching and pick the closest match rather than failing on an exact lookup (e.g. "Worcester" → "WorcesterMA", "relations" → "relationship_advice").

Reddit URLs encode structured data in their path segments. When a URL is provided, parse it directly to extract identifiers rather than making additional API calls to look them up:
- Post URLs follow the pattern /f/<forum>/<post_id>/<slug> — extract forum and post_id from the path.
- Comment URLs follow the pattern /f/<forum>/<post_id>/-/comment/<comment_id> — extract all three identifiers from the path.
- User profile URLs follow the pattern /u/<username> — extract username from the path.
Use these extracted values as literal arguments in subsequent steps. Only fall back to a lookup endpoint if the URL is not available or the required identifier cannot be read from the path.
"""

SHOPPING_HINTS = f"""
Some endpoints require an `{{sku}}` parameter. The product `{{sku}}` path is a unique string identifier for each product in the Magento database (e.g., "B086GNDL8K").
- To look up a product by its name: filter the `GET /V1/products` endpoint using the `name` field and `like` conditionType.
- To look up a product by its URL: extract the slug from the URL (e.g., "wireless-mouse-pro" from "website.com/wireless-mouse-pro.html") and filter the `GET /V1/products` endpoint using the `url_key` field and `eq` conditionType.

Many Magento endpoints return lists of items (e.g., `GET /V1/products`, `GET /V1/orders`, `GET /V1/customers/search`). To find specific items efficiently across any of these list endpoints, use the `searchCriteria` API to filter, sort, and paginate your requests:
- Filtering Logic (AND/OR):
  - OR Logic: Filters placed inside the SAME `filterGroups` index act as a logical OR. 
    * Example (SKU is "A1" OR "B2"): 
      `searchCriteria[filterGroups][0][filters][0][field]=sku&searchCriteria[filterGroups][0][filters][0][value]=A1&searchCriteria[filterGroups][0][filters][1][field]=sku&searchCriteria[filterGroups][0][filters][1][value]=B2`
  - AND Logic: Filters placed in DIFFERENT `filterGroups` indices act as a logical AND.
    * Example (Name contains "Bag" AND Price > 50): 
      `searchCriteria[filterGroups][0][filters][0][field]=name&searchCriteria[filterGroups][0][filters][0][value]=%Bag%&searchCriteria[filterGroups][0][filters][0][conditionType]=like&searchCriteria[filterGroups][1][filters][0][field]=price&searchCriteria[filterGroups][1][filters][0][value]=50&searchCriteria[filterGroups][1][filters][0][conditionType]=gt`
- Condition Types: Define how to match data using `conditionType`. Available types:
  - `eq` (equals), `neq` (not equals)
  - `gt` (greater than), `gteq` (greater than or equal), `lt` (less than), `lteq` (less than or equal)
  - `like` (SQL LIKE — wrap value in `%` wildcards, e.g., `%keyword%`), `nlike` (not like)
  - `in` (value is in a comma-separated list), `nin` (not in list). Example for `in`: `searchCriteria[filterGroups][0][filters][0][field]=sku&searchCriteria[filterGroups][0][filters][0][value]=SKU1,SKU2,SKU3&searchCriteria[filterGroups][0][filters][0][conditionType]=in`
  - `null` (field is null), `notnull` (field is not null)
  - `finset` (value exists within a comma-separated database field)
  - `from`, `to` (range boundaries)
  - When using `like`, wrap the value in literal wildcard characters (e.g., `%keyword%`). Do NOT manually URL-encode the `%` to `%25`. 
- Sorting: Dictate order using `searchCriteria[sortOrders][<index>][field]` and `searchCriteria[sortOrders][<index>][direction]` (ASC or DESC).
- Pagination: Control result pages using `searchCriteria[pageSize]` (number of items per page) and `searchCriteria[currentPage]` (1-indexed page number). Example: `searchCriteria[pageSize]=20&searchCriteria[currentPage]=1`.
- Getting all items: To fetch all items with no filters, you MUST still pass at least an empty searchCriteria: `?searchCriteria=all` or `?searchCriteria[pageSize]=50`.

CRITICAL — Search Strategy for Product Names:
  - When you need to find products by name, use the `GET /fuzzy_search` endpoint (Shopping Extra API) with the product name as the `q` parameter.
  - This returns an ordered list of product names, product SKUs, and urls, exactly as they appear on the shopping website. The item you are looking for may not be the top ranked item in the list, so make sure you check all returned results carefully.
  - You can use the returned product names to look up further details via `GET /V1/products` filtering by `name` with `eq` conditionType.
  - Keep in mind that the `GET /V1/products` might return a large amount of data for each product based on your search filters, so it is more efficient to first use the fuzzy search to find the exact product name and then filter products by that name, rather than fetching all products.

CRITICAL — POST/PUT request body structure:
The Swagger/OpenAPI schema defines body parameters with auto-generated names like "PostV1CartsQuoteIdItemsBody" or "PutV1OrdersParent_idBody". These names are NOT the JSON wrapper key. You MUST look at the `required` property inside the body parameter's `schema` to find the correct top-level JSON key.

For example, POST /V1/carts/{{cartId}}/items has a body parameter whose schema requires a "cartItem" property. The correct request body is:
  {{"cartItem": {{"sku": "...", "qty": 1, "quote_id": "..."}}}}
NOT:
  {{"PostV1CartsQuoteIdItemsBody": {{"sku": "...", "qty": 1}}}}

Common body wrapper keys by endpoint:
- POST /V1/carts/{{cartId}}/items → {{"cartItem": {{...}}}}
- POST /V1/reviews → {{"review": {{...}}}}
- POST /V1/cmsPage → {{"page": {{...}}}}
- POST /V1/cmsBlock → {{"block": {{...}}}}
- PUT /V1/orders/{{parent_id}} → {{"entity": {{...}}}}
- POST /V1/orders → {{"entity": {{...}}}}
- PUT /V1/customers/me → {{"customer": {{...}}}}

Always consult the schema's `required` field inside the body parameter definition to determine the correct JSON wrapper key.

CRITICAL — searchCriteria is REQUIRED for list endpoints:
Endpoints like `GET /V1/orders`, `GET /V1/products`, and other list/search endpoints REQUIRE the `searchCriteria` query parameter. Calling these endpoints with no query parameters at all will return HTTP 400 with "searchCriteria is required".
- Always include at least one `searchCriteria` parameter, even if you do not need any specific filters (see "Getting all items" above).

CRITICAL — You are using an Admin authentication token (not a customer token). For any task that operates on a specific customer (e.g., "add this item to my cart", "update my account info", "what is my order history"), you must resolve that customer's ID via `GET /V1/customers/search` filtering on their email, then use the customer-keyed admin endpoints below — there is no "current customer" associated with an admin token, so endpoints that try to infer one from the token will reject the request.

For cart-modifying operations specifically, the admin-token-compatible endpoints are:
- `POST /V1/customers/{{customerId}}/carts` — get-or-create the customer's active cart. Takes no body and returns a BARE INTEGER cart/quote ID (not a JSON object). Idempotent: if the customer already has an active quote, the existing ID is returned.
- `POST /V1/carts/{{cartId}}/items` — add or update a line item in that cart. Body is `{{"cartItem": {{"sku": "...", "qty": N, "quote_id": "<cartId>"}}}}`. The `quote_id` value MUST equal the `{{cartId}}` in the URL path, and `sku` is required in practice even though the JSON schema lists only `qty` and `quote_id` under `required`. Some products require option/variant selections before they can be added. Make sure to include any required options in the request body, which you can find by looking up the product's details via `GET /V1/products/{{sku}}` and checking the `options` array for any required fields.

Tasks worded as "reorder", "buy", "place an order", "purchase", or "checkout" REQUIRE actually placing an order — adding a line to a cart is NOT enough; a cart with items but no order is invisible to anything that queries the customer's orders. After populating the cart, order placement uses two more endpoints:
- `POST /V1/carts/{{cartId}}/shipping-information` — sets billing+shipping addresses and the shipping carrier/method code (commonly `flatrate`/`flatrate`). Address dicts need `region_id` (numeric, e.g. 12 for California) and `email`, not just `region_code`. This call is a prerequisite for placing the order; the response includes the available payment-method codes and totals.
- `PUT /V1/carts/{{cartId}}/order` — places the order. Body is `{{"paymentMethod": {{"method": "<code>"}}}}` using one of the payment-method codes returned above (commonly `checkmo`). Returns a BARE INTEGER order entity_id (not a JSON object). The customer-token-style `POST /V1/carts/{{cartId}}/payment-information` is not routable with an admin token — use this PUT-order endpoint instead.

CRITICAL — Use your judgement when setting the pagnination parameters `searchCriteria[pageSize]`, a small page size may not yield enough results to solve the task, while a large page size may be inefficient. The information you are looking for may not always be on the first response.
CRITICAL — Order number formatting: Magento stores order numbers (increment_id) zero-padded to 9 digits (e.g., "000000178", not "178" or "00178"). When filtering by increment_id, always zero-pad the input: str(order_number).zfill(9). For example, "00178" → "000000178", "187" → "000000187".

CRITICAL — Configurable products:
Apparel, footwear, phone cases, and similar products reject add-to-cart / add-to-wishlist with "The product's required option(s) weren't entered" unless variant options are supplied. NEVER assume a product has no options. For any task that adds a product to cart or wishlist, your plan MUST include a `GET /V1/products/{{sku}}` step BEFORE the add step to inspect the `options[]` array, even when the user did not mention size/color — many products are silently configurable. Each option has `option_id`, `title` (e.g. "Color"), `is_require`, and `values[]` where each value has `option_type_id` and `title` (e.g. "Silver"). Match the user's stated preference against the option `title` and value `title` to pick the right numeric IDs; if the user did not specify a preference, pick any in-stock value. Send required options as:
- Cart (`POST /V1/carts/{{cartId}}/items`): include `product_option.extension_attributes.custom_options: [{{"option_id": "<id>", "option_value": "<type_id>"}}, ...]` alongside `cartItem.sku`/`qty`/`quote_id`.
- Wishlist (`POST /add_to_wishlist`): pass `options: {{"<option_id>": "<option_type_id>"}}` (both as strings).
- Keep in mind that the `GET /fuzzy_search` does not return if the product has required options or not, so you may need to check the product details via `GET /V1/products/{{sku}}` to determine if you need to include options when adding to cart or wishlist.
"""
