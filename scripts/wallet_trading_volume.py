#!/usr/bin/env python3
"""
Wallet Trading Volume Analysis Script
Tracks trading volume per asset for a specific wallet across multiple timeframes
Uses Solana RPC for transaction history
"""

import requests
from datetime import datetime, timedelta
from collections import defaultdict
import json
import time
import os

# Load environment variables from .env file
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

WALLET_ADDRESS = "EZ3q7RMhCEn1iVqR7VaGUq2MmREVPU98MQPexMg4U8cq"

# APIs - Set API keys in .env file
HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY", "")
JUPITER_API_KEY = os.environ.get("JUPITER_API_KEY", "")
SOLANA_RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}" if HELIUS_API_KEY else "https://api.mainnet-beta.solana.com"
JUPITER_PRICE_API = "https://api.jup.ag/price/v3"
HELIUS_API = "https://api.helius.xyz/v0"

# Rate limiting
REQUEST_DELAY = 0.3  # seconds between RPC requests

# Well-known token addresses
KNOWN_TOKENS = {
    "So11111111111111111111111111111111111111112": "SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "mSOL",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": "WIF",
    "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr": "POPCAT",
    "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof": "RENDER",
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3": "PYTH",
    "METAewgxyPbgwsseH8T16a39CQ5VyVxZi9zXiDPY18m": "META",
    "BANKzSRVbe5NQAW9M6xD6o2SkrpCFFxbjJPEKrCv9mz": "BANK",
}

# Known DEX program IDs
DEX_PROGRAMS = {
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter v6",
    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB": "Jupiter v4",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
    "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP": "Orca",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CPMM",
}

def get_token_symbol(mint: str) -> str:
    """Get human-readable token symbol"""
    if mint in KNOWN_TOKENS:
        return KNOWN_TOKENS[mint]
    return f"{mint[:4]}...{mint[-4:]}"

def format_volume(volume: float) -> str:
    """Format large numbers for readability"""
    if volume >= 1e9:
        return f"${volume / 1e9:.2f}B"
    elif volume >= 1e6:
        return f"${volume / 1e6:.2f}M"
    elif volume >= 1e3:
        return f"${volume / 1e3:.2f}K"
    elif volume >= 1:
        return f"${volume:.2f}"
    elif volume > 0:
        return f"${volume:.4f}"
    else:
        return "$0.00"

def rpc_request(method: str, params: list) -> dict:
    """Make a Solana RPC request"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    response = requests.post(SOLANA_RPC, json=payload)
    return response.json()

def get_signatures(wallet: str, limit: int = 1000) -> list:
    """Get transaction signatures for a wallet"""
    result = rpc_request("getSignaturesForAddress", [
        wallet,
        {"limit": limit}
    ])
    return result.get("result", [])

def get_transaction(signature: str, retries: int = 3) -> dict:
    """Get parsed transaction details with retry logic"""
    for attempt in range(retries):
        try:
            time.sleep(REQUEST_DELAY)
            result = rpc_request("getTransaction", [
                signature,
                {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
            ])
            if "result" in result and result["result"]:
                return result["result"]
            if "error" in result:
                if attempt < retries - 1:
                    time.sleep(1)  # Wait longer on error
                    continue
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
    return {}

def get_jupiter_prices(mints: list) -> dict:
    """Get current prices from Jupiter V3 API"""
    if not mints:
        return {}
    try:
        ids = ",".join(mints[:100])  # Limit to 100
        headers = {}
        if JUPITER_API_KEY:
            headers["x-api-key"] = JUPITER_API_KEY

        response = requests.get(f"{JUPITER_PRICE_API}?ids={ids}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            # V3 returns prices directly with usdPrice field
            prices = {}
            for mint, info in data.items():
                if isinstance(info, dict) and "usdPrice" in info:
                    prices[mint] = {"price": info["usdPrice"]}
            return prices
    except:
        pass
    return {}

def get_helius_transaction_history(wallet: str) -> list:
    """Get ALL parsed transaction history from Helius API with pagination"""
    if not HELIUS_API_KEY:
        return []

    all_transactions = []
    base_url = f"{HELIUS_API}/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}"
    before_sig = None
    page = 1

    print("  Fetching all transactions (paginating)...")

    while True:
        try:
            url = base_url
            if before_sig:
                url += f"&before={before_sig}"

            response = requests.get(url)
            if response.status_code != 200:
                print(f"  API error: {response.status_code}")
                break

            transactions = response.json()

            if not transactions:
                break  # No more transactions

            all_transactions.extend(transactions)
            print(f"    Page {page}: fetched {len(transactions)} transactions (total: {len(all_transactions)})")

            # Get the signature of the last transaction for pagination
            last_tx = transactions[-1]
            before_sig = last_tx.get("signature")

            if not before_sig or len(transactions) < 100:
                break  # Last page

            page += 1
            time.sleep(0.2)  # Rate limiting

        except Exception as e:
            print(f"  Helius API error: {e}")
            break

    return all_transactions

def parse_helius_transactions(transactions: list, wallet: str) -> list:
    """Parse Helius transaction format for token transfers"""
    transfers = []

    for tx in transactions:
        block_time = tx.get("timestamp", 0)
        tx_type = tx.get("type", "")

        # Handle token transfers
        token_transfers = tx.get("tokenTransfers", [])
        for transfer in token_transfers:
            mint = transfer.get("mint", "")
            from_addr = transfer.get("fromUserAccount", "")
            to_addr = transfer.get("toUserAccount", "")
            amount = float(transfer.get("tokenAmount", 0))

            if not mint or amount == 0:
                continue

            if to_addr == wallet:
                transfers.append({
                    "mint": mint,
                    "change": amount,
                    "block_time": block_time,
                    "type": "buy"
                })
            elif from_addr == wallet:
                transfers.append({
                    "mint": mint,
                    "change": -amount,
                    "block_time": block_time,
                    "type": "sell"
                })

        # Handle native SOL transfers
        native_transfers = tx.get("nativeTransfers", [])
        for transfer in native_transfers:
            from_addr = transfer.get("fromUserAccount", "")
            to_addr = transfer.get("toUserAccount", "")
            amount = float(transfer.get("amount", 0)) / 1e9  # Convert lamports

            if amount < 0.001:  # Skip tiny amounts (fees)
                continue

            if to_addr == wallet:
                transfers.append({
                    "mint": "So11111111111111111111111111111111111111112",
                    "change": amount,
                    "block_time": block_time,
                    "type": "buy"
                })
            elif from_addr == wallet:
                transfers.append({
                    "mint": "So11111111111111111111111111111111111111112",
                    "change": -amount,
                    "block_time": block_time,
                    "type": "sell"
                })

    return transfers

def parse_token_transfers(tx: dict, wallet: str) -> list:
    """Parse token transfers from a transaction"""
    transfers = []

    if not tx or not tx.get("meta"):
        return transfers

    meta = tx["meta"]
    message = tx.get("transaction", {}).get("message", {})
    block_time = tx.get("blockTime", 0)

    # Check for errors
    if meta.get("err"):
        return transfers

    # Get pre and post token balances
    pre_balances = {b["accountIndex"]: b for b in meta.get("preTokenBalances", [])}
    post_balances = {b["accountIndex"]: b for b in meta.get("postTokenBalances", [])}

    # Get account keys
    account_keys = []
    if "accountKeys" in message:
        for key in message["accountKeys"]:
            if isinstance(key, str):
                account_keys.append(key)
            elif isinstance(key, dict):
                account_keys.append(key.get("pubkey", ""))

    # Find token balance changes
    all_indices = set(pre_balances.keys()) | set(post_balances.keys())

    for idx in all_indices:
        pre = pre_balances.get(idx, {})
        post = post_balances.get(idx, {})

        mint = post.get("mint") or pre.get("mint")
        owner = post.get("owner") or pre.get("owner")

        if not mint or owner != wallet:
            continue

        pre_amount = float(pre.get("uiTokenAmount", {}).get("uiAmount") or 0)
        post_amount = float(post.get("uiTokenAmount", {}).get("uiAmount") or 0)
        decimals = post.get("uiTokenAmount", {}).get("decimals") or pre.get("uiTokenAmount", {}).get("decimals") or 9

        change = post_amount - pre_amount

        if abs(change) > 0:
            transfers.append({
                "mint": mint,
                "change": change,
                "decimals": decimals,
                "block_time": block_time,
                "type": "buy" if change > 0 else "sell"
            })

    # Also check SOL balance changes
    pre_sol = meta.get("preBalances", [])
    post_sol = meta.get("postBalances", [])

    if pre_sol and post_sol and account_keys:
        for i, key in enumerate(account_keys):
            if key == wallet and i < len(pre_sol) and i < len(post_sol):
                pre_lamports = pre_sol[i]
                post_lamports = post_sol[i]
                change_sol = (post_lamports - pre_lamports) / 1e9

                # Ignore small changes (likely fees)
                if abs(change_sol) > 0.001:
                    transfers.append({
                        "mint": "So11111111111111111111111111111111111111112",
                        "change": change_sol,
                        "decimals": 9,
                        "block_time": block_time,
                        "type": "buy" if change_sol > 0 else "sell"
                    })

    return transfers

def analyze_wallet_volume(wallet: str) -> tuple:
    """Analyze trading volume per token for different timeframes"""

    now = datetime.now()
    timeframes = {
        "1d": now - timedelta(days=1),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
        "lifetime": datetime.min
    }

    # Structure: {token_mint: {timeframe: {"buy": amount, "sell": amount}}}
    volume_data = defaultdict(lambda: {
        tf: {"buy": 0, "sell": 0, "buy_usd": 0, "sell_usd": 0, "trades": 0}
        for tf in timeframes.keys()
    })

    all_transfers = []

    # Try Helius API first (much faster and more reliable)
    if HELIUS_API_KEY:
        print("Using Helius API for transaction history...")
        helius_txs = get_helius_transaction_history(wallet)
        if helius_txs:
            print(f"  Total: {len(helius_txs)} transactions fetched")
            all_transfers = parse_helius_transactions(helius_txs, wallet)
            print(f"  Parsed {len(all_transfers)} token transfers")
    else:
        print("No Helius API key configured. Using public RPC (slower, may be rate-limited)...")
        print("Tip: Get a free API key at https://helius.dev for better results\n")

        print("Fetching transaction signatures...")
        signatures = get_signatures(wallet, limit=200)
        print(f"  Found {len(signatures)} transactions")

        if signatures:
            # Limit to most recent transactions to avoid timeout
            max_tx = min(100, len(signatures))
            print(f"Analyzing {max_tx} most recent transactions (with rate limiting)...")
            signatures = signatures[:max_tx]

            processed = 0
            successful = 0

            for sig_info in signatures:
                signature = sig_info.get("signature")
                if not signature:
                    continue

                tx = get_transaction(signature)
                processed += 1

                if not tx:
                    if processed % 20 == 0:
                        print(f"  Progress: {processed}/{len(signatures)} ({successful} successful)...")
                    continue

                successful += 1
                transfers = parse_token_transfers(tx, wallet)
                all_transfers.extend(transfers)

                if processed % 20 == 0:
                    print(f"  Progress: {processed}/{len(signatures)} ({successful} successful, {len(all_transfers)} transfers)...")

            print(f"  Completed: {processed} transactions, {successful} successful, {len(all_transfers)} transfers found")

    # Process all transfers into volume data
    for transfer in all_transfers:
        mint = transfer["mint"]
        change = transfer["change"]
        block_time = transfer.get("block_time", 0)
        tx_time = datetime.fromtimestamp(block_time) if block_time else now

        for tf_name, tf_start in timeframes.items():
            if tx_time >= tf_start:
                if change > 0:
                    volume_data[mint][tf_name]["buy"] += change
                else:
                    volume_data[mint][tf_name]["sell"] += abs(change)
                volume_data[mint][tf_name]["trades"] += 1

    # Get prices for USD conversion
    all_mints = list(volume_data.keys())
    print("Fetching current prices...")
    prices = get_jupiter_prices(all_mints)

    # Calculate USD values
    for mint, tf_data in volume_data.items():
        price = float(prices.get(mint, {}).get("price", 0))
        for tf_name in tf_data:
            tf_data[tf_name]["buy_usd"] = tf_data[tf_name]["buy"] * price
            tf_data[tf_name]["sell_usd"] = tf_data[tf_name]["sell"] * price
            tf_data[tf_name]["total_usd"] = tf_data[tf_name]["buy_usd"] + tf_data[tf_name]["sell_usd"]

    return volume_data, prices

def print_volume_report(volume_data: dict, prices: dict):
    """Print formatted volume report"""

    print("\n" + "=" * 85)
    print("WALLET TRADING VOLUME ANALYSIS")
    print(f"Wallet: {WALLET_ADDRESS}")
    print("=" * 85)

    timeframes = ["1d", "7d", "30d", "lifetime"]
    timeframe_labels = {
        "1d": "24 Hours",
        "7d": "7 Days",
        "30d": "30 Days",
        "lifetime": "Lifetime"
    }

    # Filter tokens with activity
    active_tokens = {
        mint: data for mint, data in volume_data.items()
        if any(data[tf]["buy"] > 0 or data[tf]["sell"] > 0 for tf in timeframes)
    }

    if not active_tokens:
        print("\nNo trading activity found for this wallet.")
        return

    # Sort by lifetime volume
    sorted_tokens = sorted(
        active_tokens.items(),
        key=lambda x: x[1]["lifetime"].get("total_usd", 0) or (x[1]["lifetime"]["buy"] + x[1]["lifetime"]["sell"]),
        reverse=True
    )

    for mint, tf_data in sorted_tokens:
        symbol = get_token_symbol(mint)
        price = float(prices.get(mint, {}).get("price", 0))

        print(f"\n{'─' * 85}")
        print(f"TOKEN: {symbol}")
        print(f"Mint: {mint}")
        if price > 0:
            if price >= 1:
                print(f"Current Price: ${price:,.2f}")
            elif price >= 0.0001:
                print(f"Current Price: ${price:.6f}")
            else:
                print(f"Current Price: ${price:.10f}")
        print(f"{'─' * 85}")

        print(f"\n{'Timeframe':<12}{'Bought':<20}{'Sold':<20}{'Total Volume':<22}{'Trades':<8}")
        print("-" * 85)

        for tf in timeframes:
            data = tf_data[tf]
            buy = data["buy"]
            sell = data["sell"]
            total = buy + sell
            buy_usd = data.get("buy_usd", 0)
            sell_usd = data.get("sell_usd", 0)
            total_usd = data.get("total_usd", 0)
            trades = data["trades"]

            if total > 0 or trades > 0:
                # Format token amounts
                def fmt_amount(amt):
                    if amt >= 1e6:
                        return f"{amt:,.0f}"
                    elif amt >= 1:
                        return f"{amt:,.2f}"
                    elif amt > 0:
                        return f"{amt:.6f}"
                    return "—"

                buy_str = fmt_amount(buy)
                sell_str = fmt_amount(sell)
                total_str = fmt_amount(total)

                # Add USD value if available
                if total_usd > 0:
                    total_str = f"{total_str} ({format_volume(total_usd)})"

                print(f"{timeframe_labels[tf]:<12}{buy_str:<20}{sell_str:<20}{total_str:<22}{trades:<8}")
            else:
                print(f"{timeframe_labels[tf]:<12}{'—':<20}{'—':<20}{'—':<22}{'0':<8}")

    # Summary totals
    print(f"\n{'=' * 85}")
    print("SUMMARY TOTALS BY TIMEFRAME")
    print("=" * 85)

    print(f"\n{'Timeframe':<12}{'Total Bought (USD)':<22}{'Total Sold (USD)':<22}{'Total Volume (USD)':<22}")
    print("-" * 78)

    for tf in timeframes:
        total_buy = sum(data[tf].get("buy_usd", 0) for data in volume_data.values())
        total_sell = sum(data[tf].get("sell_usd", 0) for data in volume_data.values())
        total_vol = total_buy + total_sell

        print(f"{timeframe_labels[tf]:<12}{format_volume(total_buy):<22}{format_volume(total_sell):<22}{format_volume(total_vol):<22}")

    # Cumulative lifetime total
    lifetime_bought = sum(data["lifetime"].get("buy_usd", 0) for data in volume_data.values())
    lifetime_sold = sum(data["lifetime"].get("sell_usd", 0) for data in volume_data.values())
    lifetime_total = lifetime_bought + lifetime_sold
    lifetime_trades = sum(data["lifetime"].get("trades", 0) for data in volume_data.values())

    print(f"\n{'=' * 85}")
    print("CUMULATIVE LIFETIME TOTALS")
    print("=" * 85)
    print(f"\n  Total Bought:    {format_volume(lifetime_bought)}")
    print(f"  Total Sold:      {format_volume(lifetime_sold)}")
    print(f"  Total Volume:    {format_volume(lifetime_total)}")
    print(f"  Total Trades:    {lifetime_trades:,}")

    print(f"\n{'=' * 85}")
    print(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Note: USD values based on current prices, not historical prices at time of trade")
    print("=" * 85)

def main():
    print("=" * 85)
    print("SOLANA WALLET TRADING VOLUME ANALYZER")
    print("=" * 85)

    volume_data, prices = analyze_wallet_volume(WALLET_ADDRESS)
    print_volume_report(volume_data, prices)

if __name__ == "__main__":
    main()
