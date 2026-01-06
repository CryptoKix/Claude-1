#!/usr/bin/env python3
"""
Jupiter DEX Volume Query Script
Fetches trading volume data from Jupiter aggregator via DeFiLlama API
Includes per-asset volume breakdown from Birdeye API
"""

import requests
from datetime import datetime

DEFILLAMA_API = "https://api.llama.fi"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Well-known Solana token addresses
KNOWN_TOKENS = {
    "So11111111111111111111111111111111111111112": "SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "mSOL",
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs": "ETH (Wormhole)",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
    "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr": "POPCAT",
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": "WIF",
    "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof": "RENDER",
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3": "PYTH",
    "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux": "HNT",
    "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn": "jitoSOL",
    "bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1": "bSOL",
}

def get_jupiter_volume() -> dict:
    """Get Jupiter trading volume from DeFiLlama"""

    # Get summary volume data
    response = requests.get(f"{DEFILLAMA_API}/summary/dexs/jupiter?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyVolume")

    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code}")
        return {}

    return response.json()

def get_all_time_volume() -> dict:
    """Get Jupiter's all-time cumulative volume"""
    response = requests.get(f"{DEFILLAMA_API}/summary/dexs/jupiter?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=totalVolume")

    if response.status_code != 200:
        return {}

    return response.json()

def get_top_tokens_by_volume() -> list:
    """Get top traded tokens on Solana by 24h volume from CoinGecko"""

    # Get Solana ecosystem tokens sorted by volume
    response = requests.get(
        f"{COINGECKO_API}/coins/markets",
        params={
            "vs_currency": "usd",
            "category": "solana-ecosystem",
            "order": "volume_desc",
            "per_page": 20,
            "page": 1,
            "sparkline": "false"
        }
    )

    if response.status_code != 200:
        return []

    return response.json()

def get_token_name(address: str, fallback: str = None) -> str:
    """Get human-readable token name from address"""
    if address in KNOWN_TOKENS:
        return KNOWN_TOKENS[address]
    return fallback or f"{address[:6]}...{address[-4:]}"

def format_volume(volume: float) -> str:
    """Format large numbers for readability"""
    if volume >= 1e12:
        return f"${volume / 1e12:.2f}T"
    elif volume >= 1e9:
        return f"${volume / 1e9:.2f}B"
    elif volume >= 1e6:
        return f"${volume / 1e6:.2f}M"
    elif volume >= 1e3:
        return f"${volume / 1e3:.2f}K"
    else:
        return f"${volume:.2f}"

def main():
    print("=" * 60)
    print("JUPITER AGGREGATOR - TRADING VOLUME STATS")
    print("=" * 60)

    # Get daily volume data
    data = get_jupiter_volume()

    if not data:
        print("Failed to fetch Jupiter volume data")
        return

    # Display protocol info
    print(f"\nProtocol: {data.get('name', 'Jupiter')}")
    print(f"Category: {data.get('category', 'DEX Aggregator')}")
    print(f"Chains: {', '.join(data.get('chains', ['Solana']))}")

    # Current 24h volume
    total_24h = data.get('total24h', 0)
    total_48h_to_24h = data.get('total48hto24h', 0)
    total_7d = data.get('total7d', 0)
    total_30d = data.get('total30d', 0)
    all_time = data.get('totalAllTime', 0)

    print("\n" + "-" * 60)
    print("VOLUME BREAKDOWN")
    print("-" * 60)

    print(f"\n24h Volume:      {format_volume(total_24h)}")

    # Calculate 24h change
    if total_48h_to_24h and total_48h_to_24h > 0:
        change_24h = ((total_24h - total_48h_to_24h) / total_48h_to_24h) * 100
        change_symbol = "+" if change_24h >= 0 else ""
        print(f"24h Change:      {change_symbol}{change_24h:.2f}%")

    print(f"\n7d Volume:       {format_volume(total_7d)}")
    print(f"30d Volume:      {format_volume(total_30d)}")
    print(f"\nAll-Time Volume: {format_volume(all_time)}")

    # Daily average
    if total_30d:
        daily_avg = total_30d / 30
        print(f"30d Daily Avg:   {format_volume(daily_avg)}")

    # Get chain breakdown if available
    chain_data = data.get('totalDataChart', [])
    if chain_data and len(chain_data) > 0:
        print("\n" + "-" * 60)
        print("RECENT DAILY VOLUMES (Last 7 days)")
        print("-" * 60)

        # Get last 7 days
        recent_data = chain_data[-7:] if len(chain_data) >= 7 else chain_data

        for entry in recent_data:
            timestamp = entry[0]
            volume = entry[1]
            date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            print(f"  {date}: {format_volume(volume)}")

    # Protocol breakdown by version if available
    protocol_data = data.get('protocolsData', {})
    if protocol_data:
        print("\n" + "-" * 60)
        print("BREAKDOWN BY PROTOCOL VERSION")
        print("-" * 60)

        for protocol, pdata in protocol_data.items():
            vol = pdata.get('total24h', 0)
            if vol > 0:
                print(f"  {protocol}: {format_volume(vol)} (24h)")

    # Per-asset volume breakdown
    print("\n" + "-" * 60)
    print("TOP SOLANA TOKENS BY 24H TRADING VOLUME")
    print("-" * 60)

    tokens = get_top_tokens_by_volume()

    if tokens and isinstance(tokens, list):
        print(f"\n{'Rank':<6}{'Token':<14}{'Symbol':<10}{'24h Volume':<16}{'Price':<14}{'24h Change'}")
        print("-" * 75)

        for i, token in enumerate(tokens[:15], 1):
            name = token.get('name', 'Unknown')[:12]
            symbol = token.get('symbol', '???').upper()[:8]
            volume_24h = token.get('total_volume', 0) or 0
            price = token.get('current_price', 0) or 0
            change_24h = token.get('price_change_percentage_24h', 0) or 0

            # Format price based on magnitude
            if price >= 1:
                price_str = f"${price:,.2f}"
            elif price >= 0.0001:
                price_str = f"${price:.4f}"
            else:
                price_str = f"${price:.8f}"

            change_symbol = "+" if change_24h >= 0 else ""
            change_str = f"{change_symbol}{change_24h:.1f}%"

            print(f"{i:<6}{name:<14}{symbol:<10}{format_volume(volume_24h):<16}{price_str:<14}{change_str}")

        # Calculate total volume from top tokens
        total_top_volume = sum(t.get('total_volume', 0) or 0 for t in tokens[:15])
        print("-" * 75)
        print(f"{'Total (Top 15):':<30}{format_volume(total_top_volume)}")
    else:
        print("\nUnable to fetch per-asset volume data (rate limited or API error)")

    print("\n" + "=" * 60)
    print(f"Data sources: DeFiLlama, CoinGecko | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    main()
