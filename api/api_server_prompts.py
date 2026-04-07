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

Do not assume that a single project name can be used directly as `{{id}}`.
Do not assume that a parameter named `{{id}}` can be guessed or partially matched.

GitLab user `{{id}}` path parameter has exactly two directly usable forms:

- a numeric user ID, for example `2330`
- a username, for example `byteblaze`

You do NOT know your own user ID or username — if the task requires acting on "my" account, you MUST first resolve your user info using a lookup endpoint such as `GET /user` before calling endpoints any form of {{id}} or {{username}} parameter.
Do NOT pass string aliases like 'self', 'me', or 'current_user' for parameters that require an ID/username — add a prior step to look up the real value instead.
You do NOT know the user IDs or usernames of any other users — if the task requires acting on another user, you MUST first resolve that user's info using a lookup endpoint such as `GET /users?search=...` before calling endpoints with any form of {{id}} or {{username}} parameter.



When determining default_branch for a repository, do NOT assume it is always 'main' or 'master' — use the API to look up the actual default branch name.

When writing a LICENSE file to a repository :
- Use `GET /licenses` to list available license templates, or `GET /license/{{id}}` (e.g. id="mit") to fetch the exact license text — do NOT hardcode license text.
- Do NOT assume the LICENSE file already exists. Always look up the repository tree first (`GET /projects/{{id}}/repository/tree`). If a file starting with "LICENSE" is found, use action "update" with that exact filename. If no such file is found, use action "create" with a sensible filename (e.g. "LICENSE.md").

For Project Templates. Use this json schema to search through available built-in templates. Otherwise, leave template_name blank. 

{json.dumps(project_templates, indent=2)}

"""

SHOPPING_HINTS = f"""
The product `{{sku}}` path or query parameter has exactly one usable form:
- A unique string SKU, for example "B086GNDL8K"

A product name (e.g., "Wireless Mouse") or a URL key (e.g., "wireless-mouse-pro") is NOT a valid directly usable `{{sku}}` value.

Decision rule:
- If the task provides an explicit string SKU, use it directly.
- Otherwise, you MUST first resolve the product using a lookup endpoint `GET /V1/products` before calling any endpoints that require a `sku` parameter.

Do not assume that the SKU can be guessed, synthesized, or partially matched based on the product name or other attributes. 

You can use the 'GET /V1/products' endpoint to retrieve the list of all products and their SKUs. Given that the list of products may be large, you can use the 'searchCriteria' query parameters to filter the products based on name or URL key attributes to find the specific product and its SKU more efficiently.

When using the `like` conditionType in `searchCriteria`, you MUST wrap the search value in literal wildcard characters (`%`) to perform a partial match.
- CRITICAL: Do NOT chain multiple words together with wildcards (e.g., do NOT use `%Amazon%Echo%Dot%`). The search engine tokenizes product names, and a single chained multi-word wildcard query will fail to match and return 0 results.
- To search for multiple words, you MUST use a logical AND operation by placing each individual word into a separate `filterGroups` index (e.g., 0, 1, 2). 
- Example format for searching "Switch Card Case": 
  `searchCriteria[filterGroups][0][filters][0][field]=name&searchCriteria[filterGroups][0][filters][0][value]=%Switch%&searchCriteria[filterGroups][0][filters][0][conditionType]=like&searchCriteria[filterGroups][1][filters][0][field]=name&searchCriteria[filterGroups][1][filters][0][value]=%Card%&searchCriteria[filterGroups][1][filters][0][conditionType]=like&searchCriteria[filterGroups][2][filters][0][field]=name&searchCriteria[filterGroups][2][filters][0][value]=%Case%&searchCriteria[filterGroups][2][filters][0][conditionType]=like`
- Do NOT manually URL-encode the `%` to `%25`. The underlying code handles URL encoding automatically. Double-encoding will break the query.
- Do NOT omit the wildcards entirely around your terms, as this will result in an exact string match attempt and likely return no results.

CRITICAL — POST/PUT request body structure:
The Swagger/OpenAPI schema defines body parameters with auto-generated names like "PostV1CartsMineItemsBody" or "PutV1OrdersParent_idBody". These names are NOT the JSON wrapper key. You MUST look at the `required` property inside the body parameter's `schema` to find the correct top-level JSON key.

For example, POST /V1/carts/mine/items has a body parameter named "PostV1CartsMineItemsBody" whose schema requires a "cartItem" property. The correct request body is:
  {{"cartItem": {{"sku": "...", "qty": 1, "quote_id": "..."}}}}
NOT:
  {{"PostV1CartsMineItemsBody": {{"sku": "...", "qty": 1}}}}

Common body wrapper keys by endpoint:
- POST /V1/carts/mine/items → {{"cartItem": {{...}}}}
- POST /V1/reviews → {{"review": {{...}}}}
- POST /V1/cmsPage → {{"page": {{...}}}}
- POST /V1/cmsBlock → {{"block": {{...}}}}
- PUT /V1/orders/{{parent_id}} → {{"entity": {{...}}}}
- POST /V1/orders → {{"entity": {{...}}}}
- PUT /V1/customers/me → {{"customer": {{...}}}}

Always consult the schema's `required` field inside the body parameter definition to determine the correct JSON wrapper key.

CRITICAL — searchCriteria is REQUIRED for list endpoints:
Endpoints like `GET /V1/orders`, `GET /V1/products`, and other list/search endpoints REQUIRE the `searchCriteria` query parameter. Calling these endpoints with no query parameters at all will return HTTP 400 with "searchCriteria is required".
- If you want ALL results (no filtering), you MUST still pass at least an empty searchCriteria, for example: `?searchCriteria=all` or `?searchCriteria[pageSize]=20`.
- Always include at least one `searchCriteria` parameter, even if you do not need any specific filters.

CRITICAL — Adding items to cart requires a quote_id:
To add items to the shopping cart via `POST /V1/carts/mine/items`, you MUST first create/retrieve a cart by calling `POST /V1/carts/mine` (which returns an integer cart/quote ID). Then include that ID as `quote_id` in the `cartItem` object:
  Step 1: POST /V1/carts/mine → returns quote_id (e.g., 12345)
  Step 2: POST /V1/carts/mine/items with body {{"cartItem": {{"sku": "B086GNDL8K", "qty": 1, "quote_id": "12345"}}}}

CRITICAL — `/V1/customers/me` endpoint:
The `GET /V1/customers/me` and `PUT /V1/customers/me` endpoints ONLY work with customer-scoped authentication tokens. If you are using an admin token, these endpoints will fail with "customerId is required". With an admin token, you must use `GET /V1/customers/{{customerId}}` or `PUT /V1/customers/{{customerId}}` instead, and you must first look up the customer ID (e.g., via `GET /V1/customers/search` with searchCriteria filters).
"""
