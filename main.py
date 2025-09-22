import asyncio
import time
from binance.client import Client
from telegram import Bot
import requests
import json
import os

# Cấu hình
BOT_TOKEN = '8457652233:AAHGXyZULA63uRK8qZvkhkFeu7vA1-LHryo'
CHAT_ID = '-4611492878'
TIMEFRAME = '4h'
CHECK_INTERVAL = 900
NUM_PREV_CANDLES = 10
SPIKE_MULTIPLIER = 2
MAX_SYMBOLS = 100

# Khởi tạo
binance_client = Client()
telegram_bot = Bot(token=BOT_TOKEN)

# Hàm tính trung bình
def mean(numbers):
    return sum(numbers) / len(numbers) if numbers else 0

# Lấy top coins
def get_top_coins():
    url = 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=1000&page=1'
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        return [coin['symbol'].upper() for coin in data]
    except Exception as e:
        print(f"Lỗi CoinGecko: {e}")
        return []

# Lấy USDT pairs
def get_binance_usdt_symbols():
    try:
        exchange_info = binance_client.get_exchange_info()
        return [s['symbol'] for s in exchange_info['symbols'] if s['status'] == 'TRADING' and s['quoteAsset'] == 'USDT']
    except Exception as e:
        print(f"Lỗi Binance: {e}")
        return []

# Lọc symbols
def get_tracked_symbols():
    cache_file = 'symbols.json'
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                tracked = json.load(f)
                print(f"Tải {len(tracked)} symbols từ cache.")
                return tracked[:MAX_SYMBOLS]
        except:
            pass

    top_coins = get_top_coins()
    binance_symbols = get_binance_usdt_symbols()
    tracked = [s for s in binance_symbols if s[:-4] in top_coins][:MAX_SYMBOLS]
    try:
        with open(cache_file, 'w') as f:
            json.dump(tracked, f)
    except Exception as e:
        print(f"Lỗi lưu cache: {e}")
    print(f"Theo dõi {len(tracked)} symbols.")
    return tracked

# Kiểm tra volume spike
def check_volume_spike(symbol):
    try:
        klines = binance_client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=NUM_PREV_CANDLES + 1)
        volumes = [float(k[5]) for k in klines]
        prev_volumes = volumes[:-1]
        current_volume = volumes[-1]
        avg_prev = mean(prev_volumes)
        if current_volume > SPIKE_MULTIPLIER * avg_prev:
            ratio = current_volume / avg_prev
            return True, ratio
        return False, 0
    except Exception as e:
        print(f"Lỗi kiểm tra {symbol}: {e}")
        return False, 0

# Gửi alert
async def send_alert(message):
    try:
        await telegram_bot.send_message(chat_id=CHAT_ID, text=message)
        print("Alert sent!")
    except Exception as e:
        print(f"Lỗi gửi alert: {e}")

# Main loop
async def main():
    print("Bot khởi động...")
    while True:
        symbols = get_tracked_symbols()
        for symbol in symbols:
            is_spike, ratio = check_volume_spike(symbol)
            if is_spike:
                message = (
                    f"🚨 VOLUME SPIKE ALERT!\n"
                    f"Symbol: {symbol}\n"
                    f"Volume gấp {ratio:.2f}x trung bình 10 nến H4.\n"
                    f"Kiểm tra trên Binance!"
                )
                await send_alert(message)
                time.sleep(1)
            time.sleep(0.2)
        print(f"Hoàn thành kiểm tra {len(symbols)} symbols, chờ {CHECK_INTERVAL/60} phút...")
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    asyncio.run(main())
