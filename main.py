import asyncio
import time
import os
from telegram import Bot
import requests
import json
from datetime import datetime, timedelta

# Cấu hình từ biến môi trường
BOT_TOKEN = os.getenv('BOT_TOKEN', '8457652233:AAHGXyZULA63uRK8qZvkhkFeu7vA1-LHryo')
CHAT_ID = os.getenv('CHAT_ID', '-4611492878')
TIMEFRAME = '4h'  # Khung thời gian 4 giờ
CHECK_INTERVAL = 900  # 15 phút
NUM_PREV_CANDLES = 10
SPIKE_MULTIPLIER = 2
MAX_SYMBOLS = 100

# Khởi tạo Bot
telegram_bot = Bot(token=BOT_TOKEN)
print("Bot khởi động...")

# Hàm tính trung bình
def mean(numbers):
    return sum(numbers) / len(numbers) if numbers else 0

# Lấy danh sách top 1000 coins từ CoinGecko
def get_top_coins():
    url = 'https://api.coingecko.com/api/v3/coins/markets'
    params = {
        'vs_currency': 'usd',
        'order': 'market_cap_desc',
        'per_page': 1000,
        'page': 1,
        'sparkline': False
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return [coin['id'] for coin in data]  # Sử dụng 'id' của CoinGecko
    except Exception as e:
        print(f"Lỗi CoinGecko (lấy danh sách): {e}")
        return []

# Lấy dữ liệu volume lịch sử từ CoinGecko
def get_coin_volume_history(coin_id):
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=NUM_PREV_CANDLES * 4)  # 10 nến x 4h
    params = {
        'vs_currency': 'usd',
        'days': (end_time - start_time).days + 1,
        'interval': 'hourly'
    }
    url = f'https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart'
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        # Lấy volume từ dữ liệu (giả định dữ liệu trả về có trường 'total_volumes')
        volumes = [entry[1] for entry in data.get('total_volumes', [])[-NUM_PREV_CANDLES-1:]]  # Lấy 11 giá trị cuối (10 trước + hiện tại)
        return volumes
    except Exception as e:
        print(f"Lỗi CoinGecko (lấy volume {coin_id}): {e}")
        return []

# Lọc symbols và ánh xạ với CoinGecko
def get_tracked_coins():
    cache_file = 'coins.json'
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                tracked = json.load(f)
                print(f"Tải {len(tracked)} coins từ cache.")
                return tracked[:MAX_SYMBOLS]
        except:
            pass
    
    top_coins = get_top_coins()
    tracked = top_coins[:MAX_SYMBOLS]  # Lấy top 100 coins
    try:
        with open(cache_file, 'w') as f:
            json.dump(tracked, f)
    except Exception as e:
        print(f"Lỗi lưu cache: {e}")
    print(f"Theo dõi {len(tracked)} coins.")
    return tracked

# Kiểm tra volume spike
def check_volume_spike(coin_id):
    try:
        volumes = get_coin_volume_history(coin_id)
        if len(volumes) < NUM_PREV_CANDLES + 1:
            print(f"Dữ liệu volume không đủ cho {coin_id}")
            return False, 0
        prev_volumes = volumes[:-1]  # 10 nến trước
        current_volume = volumes[-1]  # Nến hiện tại
        avg_prev = mean(prev_volumes)
        if current_volume > SPIKE_MULTIPLIER * avg_prev:
            ratio = current_volume / avg_prev
            return True, ratio
        return False, 0
    except Exception as e:
        print(f"Lỗi kiểm tra {coin_id}: {e}")
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
    print("Bot đang chạy...")
    while True:
        coins = get_tracked_coins()
        for coin_id in coins:
            is_spike, ratio = check_volume_spike(coin_id)
            if is_spike:
                message = (
                    f"🚨 VOLUME SPIKE ALERT!\n"
                    f"Coin: {coin_id}\n"
                    f"Volume gấp {ratio:.2f}x trung bình 10 nến H4 (CoinGecko).\n"
                    f"Kiểm tra thêm trên CoinGecko!"
                )
                await send_alert(message)
                time.sleep(1)
            time.sleep(0.2)
        print(f"Hoàn thành kiểm tra {len(coins)} coins, chờ {CHECK_INTERVAL/60} phút...")
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    asyncio.run(main())
