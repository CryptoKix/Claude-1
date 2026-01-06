#!/usr/bin/env python3
"""
Jupiter DEX Volume Query Script
Fetches trading volume data from Jupiter aggregator via DeFiLlama API
"""

import requests
from datetime import datetime

DEFILLAMA_API = "https://api.llama.fi"

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

    print("\n" + "=" * 60)
    print(f"Data source: DeFiLlama | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    main()
