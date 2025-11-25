import asyncio, aiohttp, websockets, json
from cfg import TOKEN, CHAT_ID, RCON_IP, RCON_PORT, RCON_PASSWORD, emoji_map, MAX_LEN, RECONNECT_TIME_SLEEP

buffer = []
buffer_lock = asyncio.Lock()

API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

async def send_telegram_message(text: str):

    while text:
        if len(text) <= MAX_LEN:
            part = text
            text = ""
        else:
            # Находим последний '\n' перед MAX_LEN
            split_pos = text.rfind('\n', 0, MAX_LEN)
            if split_pos == -1:
                split_pos = MAX_LEN
            part = text[:split_pos]
            text = text[split_pos + 1:] if '\n' in text[:MAX_LEN] else text[MAX_LEN:]

        if not part:
            continue

        params = {
            "chat_id": CHAT_ID,
            "text": part,
            "parse_mode": "HTML"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(API_URL, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"[ERROR] Ошибка отправки в Telegram: {response.status} - {error_text}")
        except aiohttp.ClientError as e:
            print(f"[ERROR] Сетевая ошибка в send_telegram_message: {e}")
        except Exception as e:
            print(f"[ERROR] Неизвестная ошибка в send_telegram_message: {e}")

def format_response(response_type: str, response: str) -> str:
    emoji = emoji_map.get(response_type, "ℹ️")
    return f"{emoji} {response}"

async def buffer_sender():
    while True:
        await asyncio.sleep(4)
        async with buffer_lock:
            if buffer:
                combined_msg = '\n'.join(buffer)
                await send_telegram_message(combined_msg)
                buffer.clear()

async def get_console():
    sender_task = None
    while True:  # цикл для переподключения
        try:
            async with websockets.connect(f"ws://{RCON_IP}:{RCON_PORT}/{RCON_PASSWORD}") as ws:
                print(f"[INFO] connected.")
                if sender_task is None or sender_task.done():
                    sender_task = asyncio.create_task(buffer_sender())

                async for message in ws:
                    try:
                        data = json.loads(message)
                        response = data.get("Message", "")
                        response_type = data.get("Type", "")
                        if response:  # Только если есть сообщение
                            resp = format_response(response_type, response)
                            async with buffer_lock:
                                buffer.append(resp)
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Ошибка парсинга JSON: {e} (сообщение: {message})")
                    except Exception as e:
                        print(f"[ERROR] Ошибка обработки сообщения: {e}")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[ERROR] Соединение закрыто: {e}. Переподключаюсь через {RECONNECT_TIME_SLEEP} сек...")
        except Exception as e:
            print(f"[ERROR] Ошибка в get_console: {e}. Переподключаюсь через {RECONNECT_TIME_SLEEP} сек...")
        finally:
            await asyncio.sleep(RECONNECT_TIME_SLEEP)  # Задержка перед переподключением

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    sender_task = None
    try:
        sender_task = loop.create_task(buffer_sender())
        loop.run_until_complete(get_console())
    except KeyboardInterrupt:
        print(f"[ERROR] Скрипт остановлен пользователем.")
        if buffer:
            combined_msg = '\n'.join(buffer)
            loop.run_until_complete(send_telegram_message(combined_msg))
        if sender_task:
            sender_task.cancel()
    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {e}")
    finally:
        loop.close()