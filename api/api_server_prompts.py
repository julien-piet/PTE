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
  - Database titles may omit certain words (e.g., "Amazon" might not be in the title for "Echo Dot 3rd Gen"). If you use a strict AND query for every single word in a long phrase, you will likely get 0 results. 
  - Be strategic: Select 1 to 3 CORE identifying keywords from the target product name (e.g., "Echo" and "Dot"). Place each of these core words into a separate `filterGroups` index to perform a logical AND.
  - Do NOT chain multiple words together with wildcards (e.g., do NOT use `%Amazon%Echo%`).
  - Fallback Strategy: If your initial AND search returns 0 items, broaden your search by dropping the least unique word (like a brand name) or switching to an OR logic for related terms.

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
- Always include at least one `searchCriteria` parameter, even if you do not need any specific filters (see "Getting all items" above).

CRITICAL — For tasks that require a user-specific customer operation (e.g., "add this item to my cart", "update my account info", "what is my order history"), your customer email is "emma.lopez@gmail.com" and you MUST first look up her customer ID using `GET /V1/customers/search` with appropriate filters (e.g., `searchCriteria[filterGroups][0][filters][0][field]=email&searchCriteria[filterGroups][0][filters][0][value]=emma.lopez@example.com`). You cannot assume or guess the customer ID, and you cannot use "self", "me", or any other alias in place of the actual customer ID.
CRITICAL — Use your judgement when setting the pagnination parameters `searchCriteria[pageSize]`, a small page size may not yield enough results to solve the task, while a large page size may be inefficient. The information you are looking for may not always be on the first response.
"""
