#!/usr/bin/env python3
"""
Standalone script to authenticate and save tokens to .env file.
Run this script to login and save authentication tokens.

Usage:
    python authenticate.py
    python authenticate.py --customer-only
    python authenticate.py --admin-only
"""

import argparse
import asyncio
from pathlib import Path

from agent.common.configurator import Configurator
from agent.common.tool_manager import initialize_tools
from agent.common.token_manager import TokenStore, authenticate_and_save_tokens


async def main():
    parser = argparse.ArgumentParser(description="Authenticate and save tokens to .env file")
    parser.add_argument("--customer-only", action="store_true", help="Only authenticate customer")
    parser.add_argument("--admin-only", action="store_true", help="Only authenticate admin")
    parser.add_argument("--customer-username", type=str, help="Customer username (will prompt if not provided)")
    parser.add_argument("--customer-password", type=str, help="Customer password (will prompt if not provided)")
    parser.add_argument("--admin-username", type=str, help="Admin username (will prompt if not provided)")
    parser.add_argument("--admin-password", type=str, help="Admin password (will prompt if not provided)")
    parser.add_argument("--no-save", action="store_true", help="Don't save to .env file (only store in TokenStore)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Authentication Token Setup")
    print("=" * 60)
    
    # Load configuration
    config = Configurator()
    config.load_client_env()
    config.load_shared_env()
    config.load_server_env()  # Load server tokens from .server_env
    config.check_llm_env_vars()
    
    # Initialize tools
    print("\nInitializing tools...")
    tools, token_store = await initialize_tools(config)
    
    # Determine what to authenticate
    customer_username = args.customer_username if not args.admin_only else None
    customer_password = args.customer_password if not args.admin_only else None
    admin_username = args.admin_username if not args.customer_only else None
    admin_password = args.admin_password if not args.customer_only else None
    
    if args.customer_only:
        admin_username = None
        admin_password = None
    elif args.admin_only:
        customer_username = None
        customer_password = None
    
    # Authenticate and save tokens
    tokens = await authenticate_and_save_tokens(
        tools=tools,
        token_store=token_store,
        config=config,
        customer_username=customer_username,
        customer_password=customer_password,
        admin_username=admin_username,
        admin_password=admin_password,
        save_to_env=not args.no_save,
        skip_customer=args.admin_only,
        skip_admin=args.customer_only
    )
    
    # Summary - check both newly obtained tokens and existing tokens from TokenStore
    print("\n" + "=" * 60)
    print("Authentication Summary")
    print("=" * 60)
    
    # Check for customer token (newly obtained or existing)
    customer_token = tokens["customer_token"] or token_store.get_token("shopping", "customer")
    if customer_token:
        if tokens["customer_token"]:
            print("✓ Customer token: Obtained and saved")
        else:
            print("✓ Customer token: Already exists (from previous authentication)")
    else:
        print("✗ Customer token: Not obtained")
    
    # Check for admin token (newly obtained or existing)
    admin_token = tokens["admin_token"] or token_store.get_token("shopping", "admin")
    if admin_token:
        if tokens["admin_token"]:
            print("✓ Admin token: Obtained and saved")
        else:
            print("✓ Admin token: Already exists (from previous authentication)")
    else:
        print("✗ Admin token: Not obtained")
    
    if not args.no_save:
        env_path = Path(config.project_root) / config.get_key('server_env_path')
        print(f"\nTokens saved to: {env_path}")
        print("You can now use these tokens in your agent sessions.")
    else:
        print("\nTokens stored in TokenStore only (not saved to .server_env file)")


if __name__ == "__main__":
    asyncio.run(main())
