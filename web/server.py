#!/usr/bin/env python3
"""
Solana Wallet Dashboard - Simple HTTP Server
No external dependencies required
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import requests
import os
from datetime import datetime, timedelta
from collections import defaultdict
import time
from urllib.parse import urlparse, parse_qs

# Load environment variables
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
HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY", "")
JUPITER_API_KEY = os.environ.get("JUPITER_API_KEY", "")
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
JUPITER_PRICE_API = "https://api.jup.ag/price/v3"
HELIUS_API = "https://api.helius.xyz/v0"

KNOWN_TOKENS = {
    "So11111111111111111111111111111111111111112": "SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "mSOL",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
    "METAewgxyPbgwsseH8T16a39CQ5VyVxZi9zXiDPY18m": "META",
    "BANKJmvhT8tiJRsBSS1n2HryMBPvT5Ze4HU95DUAmeta": "BANK",
}

def get_token_symbol(mint):
    if mint in KNOWN_TOKENS:
        return KNOWN_TOKENS[mint]
    return f"{mint[:4]}...{mint[-4:]}"

def get_jupiter_prices(mints):
    if not mints:
        return {}
    try:
        ids = ",".join(mints[:100])
        headers = {"x-api-key": JUPITER_API_KEY} if JUPITER_API_KEY else {}
        response = requests.get(f"{JUPITER_PRICE_API}?ids={ids}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            prices = {}
            for mint, info in data.items():
                if isinstance(info, dict) and "usdPrice" in info:
                    prices[mint] = info["usdPrice"]
            return prices
    except:
        pass
    return {}

def get_sol_balance():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [WALLET_ADDRESS]
    }
    response = requests.post(SOLANA_RPC, json=payload)
    result = response.json()
    if "result" in result:
        return result["result"]["value"] / 1e9
    return 0.0

def get_token_accounts():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            WALLET_ADDRESS,
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
            if balance > 0:
                tokens.append({"mint": mint, "balance": balance})
    return tokens

def get_helius_transactions():
    if not HELIUS_API_KEY:
        return []

    all_transactions = []
    base_url = f"{HELIUS_API}/addresses/{WALLET_ADDRESS}/transactions?api-key={HELIUS_API_KEY}"
    before_sig = None

    while True:
        try:
            url = base_url + (f"&before={before_sig}" if before_sig else "")
            response = requests.get(url)
            if response.status_code != 200:
                break
            transactions = response.json()
            if not transactions:
                break
            all_transactions.extend(transactions)
            before_sig = transactions[-1].get("signature")
            if not before_sig or len(transactions) < 100:
                break
            time.sleep(0.1)
        except:
            break

    return all_transactions

def parse_transfers(transactions):
    transfers = []
    for tx in transactions:
        block_time = tx.get("timestamp", 0)

        for transfer in tx.get("tokenTransfers", []):
            mint = transfer.get("mint", "")
            from_addr = transfer.get("fromUserAccount", "")
            to_addr = transfer.get("toUserAccount", "")
            amount = float(transfer.get("tokenAmount", 0))

            if not mint or amount == 0:
                continue

            if to_addr == WALLET_ADDRESS:
                transfers.append({"mint": mint, "amount": amount, "type": "buy", "timestamp": block_time})
            elif from_addr == WALLET_ADDRESS:
                transfers.append({"mint": mint, "amount": amount, "type": "sell", "timestamp": block_time})

        for transfer in tx.get("nativeTransfers", []):
            from_addr = transfer.get("fromUserAccount", "")
            to_addr = transfer.get("toUserAccount", "")
            amount = float(transfer.get("amount", 0)) / 1e9

            if amount < 0.001:
                continue

            sol_mint = "So11111111111111111111111111111111111111112"
            if to_addr == WALLET_ADDRESS:
                transfers.append({"mint": sol_mint, "amount": amount, "type": "buy", "timestamp": block_time})
            elif from_addr == WALLET_ADDRESS:
                transfers.append({"mint": sol_mint, "amount": amount, "type": "sell", "timestamp": block_time})

    return transfers

def get_balance_data():
    sol_balance = get_sol_balance()
    tokens = get_token_accounts()

    sol_mint = "So11111111111111111111111111111111111111112"
    all_mints = [sol_mint] + [t["mint"] for t in tokens]
    prices = get_jupiter_prices(all_mints)

    portfolio = []
    total_value = 0

    sol_price = prices.get(sol_mint, 0)
    sol_value = sol_balance * sol_price
    total_value += sol_value
    portfolio.append({
        "symbol": "SOL",
        "mint": sol_mint,
        "balance": sol_balance,
        "price": sol_price,
        "value": sol_value
    })

    for token in tokens:
        mint = token["mint"]
        balance = token["balance"]
        price = prices.get(mint, 0)
        value = balance * price
        total_value += value

        portfolio.append({
            "symbol": get_token_symbol(mint),
            "mint": mint,
            "balance": balance,
            "price": price,
            "value": value
        })

    portfolio.sort(key=lambda x: x["value"], reverse=True)

    return {
        "wallet": WALLET_ADDRESS,
        "portfolio": portfolio,
        "total_value": total_value,
        "updated": datetime.now().isoformat()
    }

def get_volume_data():
    now = datetime.now()
    timeframes = {
        "1d": now - timedelta(days=1),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
        "lifetime": datetime.min
    }

    transactions = get_helius_transactions()
    transfers = parse_transfers(transactions)

    volume_data = defaultdict(lambda: {
        tf: {"buy": 0, "sell": 0, "trades": 0}
        for tf in timeframes.keys()
    })

    for transfer in transfers:
        mint = transfer["mint"]
        amount = transfer["amount"]
        tx_time = datetime.fromtimestamp(transfer["timestamp"]) if transfer["timestamp"] else now

        for tf_name, tf_start in timeframes.items():
            if tx_time >= tf_start:
                if transfer["type"] == "buy":
                    volume_data[mint][tf_name]["buy"] += amount
                else:
                    volume_data[mint][tf_name]["sell"] += amount
                volume_data[mint][tf_name]["trades"] += 1

    all_mints = list(volume_data.keys())
    prices = get_jupiter_prices(all_mints)

    tokens_volume = []
    totals = {tf: {"buy": 0, "sell": 0, "total": 0, "trades": 0} for tf in timeframes.keys()}

    for mint, tf_data in volume_data.items():
        price = prices.get(mint, 0)
        token_vol = {
            "symbol": get_token_symbol(mint),
            "mint": mint,
            "price": price,
            "timeframes": {}
        }

        for tf_name, data in tf_data.items():
            buy_usd = data["buy"] * price
            sell_usd = data["sell"] * price
            total_usd = buy_usd + sell_usd

            token_vol["timeframes"][tf_name] = {
                "buy": data["buy"],
                "sell": data["sell"],
                "buy_usd": buy_usd,
                "sell_usd": sell_usd,
                "total_usd": total_usd,
                "trades": data["trades"]
            }

            totals[tf_name]["buy"] += buy_usd
            totals[tf_name]["sell"] += sell_usd
            totals[tf_name]["total"] += total_usd
            totals[tf_name]["trades"] += data["trades"]

        tokens_volume.append(token_vol)

    tokens_volume.sort(key=lambda x: x["timeframes"]["lifetime"]["total_usd"], reverse=True)

    return {
        "wallet": WALLET_ADDRESS,
        "tokens": tokens_volume[:20],
        "totals": totals,
        "transaction_count": len(transactions),
        "updated": datetime.now().isoformat()
    }

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(__file__), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open(os.path.join(os.path.dirname(__file__), 'index.html'), 'rb') as f:
                self.wfile.write(f.read())

        elif parsed.path == '/api/balance':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = get_balance_data()
            self.wfile.write(json.dumps(data).encode())

        elif parsed.path == '/api/volume':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = get_volume_data()
            self.wfile.write(json.dumps(data).encode())

        else:
            super().do_GET()

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

if __name__ == '__main__':
    port = 8000
    print(f"=" * 60)
    print(f"Solana Wallet Dashboard")
    print(f"=" * 60)
    print(f"\nStarting server at http://localhost:{port}")
    print(f"Wallet: {WALLET_ADDRESS}")
    print(f"\nPress Ctrl+C to stop\n")

    server = HTTPServer(('localhost', port), DashboardHandler)
    server.serve_forever()
