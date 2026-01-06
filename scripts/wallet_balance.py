#!/usr/bin/env python3
"""
Solana Wallet Balance Query Script
Queries SOL and token balances using Solana RPC and Jupiter Price API
"""

import requests
import json

WALLET_ADDRESS = "EZ3q7RMhCEn1iVqR7VaGUq2MmREVPU98MQPexMg4U8cq"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
JUPITER_PRICE_API = "https://api.jup.ag/price/v2"

def get_sol_balance(wallet_address: str) -> float:
    """Get SOL balance for a wallet address"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [wallet_address]
    }

    response = requests.post(SOLANA_RPC, json=payload)
    result = response.json()

    if "result" in result:
        lamports = result["result"]["value"]
        return lamports / 1e9  # Convert lamports to SOL
    return 0.0

def get_token_accounts(wallet_address: str) -> list:
    """Get all SPL token accounts for a wallet"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet_address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"}
        ]
    }

    response = requests.post(SOLANA_RPC, json=payload)
    result = response.json()

    tokens = []
    if "result" in result and result["result"]["value"]:
        for account in result["result"]["value"]:
            token_data = account["account"]["data"]["parsed"]["info"]
            mint = token_data["mint"]
            balance = float(token_data["tokenAmount"]["uiAmount"] or 0)
            decimals = token_data["tokenAmount"]["decimals"]

            if balance > 0:
                tokens.append({
                    "mint": mint,
                    "balance": balance,
                    "decimals": decimals
                })

    return tokens

def get_jupiter_prices(mint_addresses: list) -> dict:
    """Get token prices from Jupiter Price API"""
    if not mint_addresses:
        return {}

    ids = ",".join(mint_addresses)
    response = requests.get(f"{JUPITER_PRICE_API}?ids={ids}")

    if response.status_code == 200:
        data = response.json()
        return data.get("data", {})
    return {}

def main():
    print(f"Querying wallet: {WALLET_ADDRESS}\n")
    print("=" * 60)

    # Get SOL balance
    sol_balance = get_sol_balance(WALLET_ADDRESS)
    print(f"\nSOL Balance: {sol_balance:.9f} SOL")

    # Get SOL price from Jupiter
    sol_mint = "So11111111111111111111111111111111111111112"
    sol_price_data = get_jupiter_prices([sol_mint])

    if sol_mint in sol_price_data:
        sol_price = float(sol_price_data[sol_mint].get("price", 0))
        sol_value = sol_balance * sol_price
        print(f"SOL Price: ${sol_price:.2f}")
        print(f"SOL Value: ${sol_value:.2f}")

    # Get token accounts
    print("\n" + "=" * 60)
    print("\nSPL Token Balances:")
    print("-" * 60)

    tokens = get_token_accounts(WALLET_ADDRESS)

    if not tokens:
        print("No SPL tokens found")
    else:
        # Get prices for all tokens
        mints = [t["mint"] for t in tokens]
        prices = get_jupiter_prices(mints)

        total_value = sol_balance * sol_price if sol_mint in sol_price_data else 0

        for token in tokens:
            mint = token["mint"]
            balance = token["balance"]

            price_info = prices.get(mint, {})
            price = float(price_info.get("price", 0))
            value = balance * price
            total_value += value

            # Truncate mint for display
            short_mint = f"{mint[:8]}...{mint[-4:]}"

            print(f"\nMint: {short_mint}")
            print(f"  Balance: {balance:,.6f}")
            if price > 0:
                print(f"  Price: ${price:.6f}")
                print(f"  Value: ${value:.2f}")

        print("\n" + "=" * 60)
        print(f"\nTotal Portfolio Value: ${total_value:.2f}")

if __name__ == "__main__":
    main()
