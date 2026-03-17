<!-- # PTE -->

<!-- ## How to add a new API

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

If you omit the SKU, the script prompts interactively. Provide `--quote-id` to reuse an existing cart; otherwise it creates one for you, clears any existing line items, adds the SKU, and then fetches the cart contents to ensure the product actually landed in the cart (fails loudly if it did not). -->

# PTE (Plan-Then-Execute) Agent

A LangGraph-based agent that plans and executes tasks using MCP (Model Context Protocol) servers for website automation.

## Prerequisites

1. **Python 3.12+** (recommended)
2. **Virtual Environment** (already set up in `venv/`)
3. **Dependencies** - Install from `config/pip_requirements.txt`:
   ```bash
   pip install -r config/pip_requirements.txt
   ```

## Configuration

1. **Environment Variables**: Set up your configuration files in the `config/` directory:
   - `config/.env` - Client environment variables (LLM API keys, etc.)
   - `config/.mcpenv` - MCP server environment variables
   - `config/.sharedenv` - Shared environment variables

2. **LLM Provider Setup**: Configure your LLM provider in `config/config.yaml`:
   - Set `agent_llm_provider` (options: `openai`, `anthropic`, `google`)
   - Set `agent_llm_model` to your preferred model
   - Add your API keys to the appropriate `.env` file

3. **MCP Server Configuration**: In `config/config.yaml`, configure your MCP servers:
   ```yaml
   mcp_server:
     webarena: http://localhost:8000/
   ```

## Running the Agent

### Step 1: Start MCP Servers

First, you need to start the MCP servers that provide the tools the agent will use. Each server runs on a separate port.

**Start the shopping server:**
```bash
python3 -m servers.shopping_server 
```

This will start the WebArena MCP server on `http://localhost:8000/` (as configured in `config.yaml`).

> **Note**: Keep this terminal window open while using the agent. The server must be running for the agent to access tools.

### Step 2: Run the Agent

In a **new terminal window**, activate the virtual environment and run the agent:

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Run the agent
python3 python3 -m agent.agent_replan
```

The agent will:
1. Load configuration and connect to MCP servers
2. Initialize available tools
3. Start an interactive session where you can type your tasks

### Optional: Authentication Setup

Before running the agent for the first time, authenticate and save tokens:

```bash
python3 authenticate.py
```

Options:
- `--customer-only` - Only authenticate customer account
- `--admin-only` - Only authenticate admin account
- `--customer-username USERNAME` - Provide customer username
- `--customer-password PASSWORD` - Provide customer password
- `--admin-username USERNAME` - Provide admin username
- `--admin-password PASSWORD` - Provide admin password
- `--no-save` - Don't save tokens to .env file

## Usage Example

1. **Terminal 1** - Start the MCP server:
   ```bash
   python servers/shopping_server.py
   ```

2. **Terminal 2** - Run the agent:
   ```bash
   python agent/agent_replan.py
   ```

3. **In the agent terminal**, type your task:
   ```
   You: Search for products with "laptop" in the name
   ```

The agent will:
- Route to appropriate website APIs
- Create an execution plan
- Analyze requirements
- Execute the plan using available tools
- Provide a response

Type `exit`, `quit`, or press `Ctrl+C` to stop the agent.

## Project Structure

- `agent/agent_replan.py` - Main agent implementation (LangGraph-based)
- `servers/` - MCP server implementations
- `api/` - API module definitions
- `config/` - Configuration files and environment variables
- `authenticate.py` - Authentication script for setting up tokens

## How to Add a New API

Go to `/api`, duplicate the template (`api/template.py`) and follow the instructions at the top of the file. Do this in a new branch, and submit a PR when you are done with a website.