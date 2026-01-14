import websockets, json, asyncio, aiohttp
from collections import defaultdict

from cfg import RECONNECT_TIME_SLEEP, MAX_LEN, TOKEN, emoji_map, tg_log_thread_id_map, RCON_IP, RCON_PORT, RCON_PASSWORD, CHAT_ID

ws = None
buffer = defaultdict(list)
buffer_lock = asyncio.Lock()

tg_token = TOKEN
tg_log_chanel_id = CHAT_ID
tg_log_thread_id_map = tg_log_thread_id_map

message_queue = asyncio.Queue(maxsize=10000)
log_queue = asyncio.Queue(maxsize=10000)

API_URL = f"https://api.telegram.org/bot{tg_token}/sendMessage"

"""=======================================
            CONNECT TO RCON
======================================="""
async def connecter_to_ws(ip, rcon_port, rcon_paswd):
    global ws
    websocket_url = f"ws://{ip}:{rcon_port}/{rcon_paswd}"
    while True:
        try:
            async with websockets.connect(websocket_url, close_timeout=0.1) as ws:
                print("[INFO] connected")
                async for message in ws:
                    await message_queue.put(message)

        except (websockets.ConnectionClosedError, websockets.ConnectionClosedOK) as e:
            pass
        except ConnectionRefusedError:
            print("[WARNING] Server off")
            await asyncio.sleep(6)
        except Exception as e:
            print("[WARNING] Unexpected error:", e)

        finally:
            if ws is not None:
                ws = None
            # Очистка очереди при разрыве
            for q in (message_queue, log_queue):
                while not q.empty():
                    try:
                        q.get_nowait()
                    except asyncio.queues.QueueEmpty:
                        pass

            await asyncio.sleep(RECONNECT_TIME_SLEEP)

async def dispatcher():
    """ распределение """
    while True:
        message = await message_queue.get()
        try:
            if not message or message.strip() == "": # пропуск пустого сообщение
                continue
            data = json.loads(message)
            identifier = data.get("Identifier", 0)
            if identifier in [0, -1, 50]:
                await log_queue.put(data)
            # тут можно доп условие сделать по identifier
        except json.JSONDecodeError as e:
            print(f"[ERROR] Bad JSON in message: {e} (message: {message})")
        except Exception as e:
            print(f"[ERROR] Dispatcher error: {e}")

async def send_telegram_message(text: str, thread_id: str):
    """ ЛОГ В ТГ """
    global tg_log_chanel_id

    while text:
        if len(text) <= MAX_LEN:
            part = text
            text = ""
        else:
            split_pos = text.rfind('\n', 0, MAX_LEN)
            if split_pos == -1:
                split_pos = MAX_LEN
            part = text[:split_pos]
            text = text[split_pos + 1:] if '\n' in text[:MAX_LEN] else text[MAX_LEN:]

        if not part:
            continue

        params = {
            "chat_id": tg_log_chanel_id,
            "text": part,
            "parse_mode": "HTML"
        }
        if thread_id is not None:
            params["message_thread_id"] = thread_id
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
    """ добавление эмодзи перед сообщением """
    emoji = emoji_map.get(response_type, "ℹ️")
    return f"{emoji} {response}"

def get_thread_id(response_type: str) -> str:
    """ распределение сообщений по топикам """
    channel = tg_log_thread_id_map.get(response_type)
    if channel is None:
        channel = tg_log_thread_id_map.get("Generic")
    return channel

async def buffer_sender():
    while True:
        await asyncio.sleep(4) # задержка, чтоб не ловить ошибки от tg / минимум - 4 сек (к запросу в тг можно прикинуть прокси и делать меньше задержку)
        async with buffer_lock:
            data_to_send = {
                rt: msgs.copy()
                for rt, msgs in buffer.items()
                if msgs
            }
            buffer.clear()

        for response_type, messages in data_to_send.items():
            thread_id = get_thread_id(response_type)
            combined_msg = '\n'.join(messages)
            await send_telegram_message(combined_msg, thread_id)


async def get_console():
    asyncio.create_task(buffer_sender())
    while True:
        try:
            data = await log_queue.get()
            response = data.get("Message", "")
            response_type = data.get("Type", "Generic")
            if response:
                if response_type == "Chat":
                    response = json.loads(response)

                    author_message_ = response.get("Username", "Unknow")
                    author_steam_id_ = response.get("UserId", "")
                    message_ = response.get("Message", "")

                    response = f"{author_message_} (`{author_steam_id_}`): {message_}"
                resp = format_response(response_type, response)
                async with buffer_lock:
                    buffer[response_type].append(resp)

        except Exception as e:
            print(f"[ERROR] Ошибка обработки log сообщения: {e}")

async def init_rcon_logger():
    if isinstance(RCON_PASSWORD, str) and RCON_PASSWORD.strip() != "enter_rcon_password":
        # поток подключия+чтения
        asyncio.create_task(connecter_to_ws(ip=RCON_IP, rcon_port=RCON_PORT, rcon_paswd=RCON_PASSWORD))
        # поток распределения
        asyncio.create_task(dispatcher())

        # ждём конект, и запускаем поток логгера
        await asyncio.sleep(4)
        asyncio.create_task(get_console())
    else:
        print("[WARNING] RCON password is empty, logger not initialized")