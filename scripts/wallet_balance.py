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
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Known token symbols
KNOWN_TOKENS = {
    "So11111111111111111111111111111111111111112": "SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "mSOL",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
    "METAewgxyPbgwsseH8T16a39CQ5VyVxZi9zXiDPY18m": "META",
}

def get_token_symbol(mint: str) -> str:
    """Get token symbol from mint address"""
    if mint in KNOWN_TOKENS:
        return KNOWN_TOKENS[mint]
    return f"{mint[:4]}...{mint[-4:]}"

def format_price(price: float) -> str:
    """Format price based on magnitude"""
    if price >= 1:
        return f"${price:,.2f}"
    elif price >= 0.0001:
        return f"${price:.6f}"
    elif price > 0:
        return f"${price:.10f}"
    return "N/A"

def format_value(value: float) -> str:
    """Format USD value"""
    if value >= 1:
        return f"${value:,.2f}"
    elif value > 0:
        return f"${value:.4f}"
    return "$0.00"

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
        if "data" in data:
            return data.get("data", {})
    return {}

def get_prices(mint_addresses: list) -> dict:
    """Get token prices - tries Jupiter first, then CoinGecko"""
    prices = {}

    # Try Jupiter first
    jupiter_prices = get_jupiter_prices(mint_addresses)
    if jupiter_prices:
        return jupiter_prices

    # Fallback to CoinGecko
    # Map of mint addresses to CoinGecko IDs
    coingecko_ids = {
        "So11111111111111111111111111111111111111112": "solana",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "usd-coin",
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "tether",
        "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "jupiter-exchange-solana",
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "bonk",
        "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "msol",
    }

    # Get CoinGecko IDs for mints we have
    ids_to_fetch = []
    mint_to_cg = {}
    for mint in mint_addresses:
        if mint in coingecko_ids:
            cg_id = coingecko_ids[mint]
            ids_to_fetch.append(cg_id)
            mint_to_cg[cg_id] = mint

    if ids_to_fetch:
        try:
            ids_str = ",".join(ids_to_fetch)
            response = requests.get(
                f"{COINGECKO_API}/simple/price?ids={ids_str}&vs_currencies=usd"
            )
            if response.status_code == 200:
                data = response.json()
                for cg_id, price_data in data.items():
                    if cg_id in mint_to_cg:
                        mint = mint_to_cg[cg_id]
                        prices[mint] = {"price": price_data.get("usd", 0)}
        except Exception as e:
            pass

    # For tokens not in CoinGecko, try to get price via Solana contract
    remaining = [m for m in mint_addresses if m not in prices]
    if remaining:
        try:
            addresses = ",".join(remaining)
            response = requests.get(
                f"{COINGECKO_API}/simple/token_price/solana?contract_addresses={addresses}&vs_currencies=usd"
            )
            if response.status_code == 200:
                data = response.json()
                for mint, price_data in data.items():
                    prices[mint] = {"price": price_data.get("usd", 0)}
        except:
            pass

    return prices

def main():
    print("=" * 75)
    print("SOLANA WALLET BALANCE")
    print(f"Wallet: {WALLET_ADDRESS}")
    print("=" * 75)

    # Get SOL balance
    sol_balance = get_sol_balance(WALLET_ADDRESS)
    sol_mint = "So11111111111111111111111111111111111111112"

    # Get token accounts
    tokens = get_token_accounts(WALLET_ADDRESS)

    # Get all prices at once (including SOL)
    all_mints = [sol_mint] + [t["mint"] for t in tokens]
    prices = get_prices(all_mints)

    # Calculate SOL value
    sol_price = float(prices.get(sol_mint, {}).get("price", 0))
    sol_value = sol_balance * sol_price

    # Build portfolio data
    portfolio = [{
        "symbol": "SOL",
        "mint": sol_mint,
        "balance": sol_balance,
        "price": sol_price,
        "value": sol_value
    }]

    for token in tokens:
        mint = token["mint"]
        balance = token["balance"]
        price = float(prices.get(mint, {}).get("price", 0))
        value = balance * price

        portfolio.append({
            "symbol": get_token_symbol(mint),
            "mint": mint,
            "balance": balance,
            "price": price,
            "value": value
        })

    # Sort by value (highest first)
    portfolio.sort(key=lambda x: x["value"], reverse=True)

    # Print table header
    print(f"\n{'Token':<12}{'Balance':<20}{'Price':<16}{'Value (USD)':<15}")
    print("-" * 75)

    total_value = 0
    for item in portfolio:
        symbol = item["symbol"]
        balance = item["balance"]
        price = item["price"]
        value = item["value"]
        total_value += value

        # Format balance
        if balance >= 1000000:
            bal_str = f"{balance:,.0f}"
        elif balance >= 1:
            bal_str = f"{balance:,.4f}"
        else:
            bal_str = f"{balance:.9f}"

        print(f"{symbol:<12}{bal_str:<20}{format_price(price):<16}{format_value(value):<15}")

    # Print total
    print("-" * 75)
    print(f"{'TOTAL':<12}{'':<20}{'':<16}{format_value(total_value):<15}")
    print("=" * 75)

if __name__ == "__main__":
    main()
