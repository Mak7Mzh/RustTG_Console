import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from cfg import TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def get_group_id(message: types.Message):
    chat_title = message.chat.title or "ЛС"
    await message.answer(
        f"{chat_title}\n"
        f"chat_id: {message.chat.id}\n"
        f"thread_id: {message.message_thread_id}\n"
    )

async def full_main():
    from console import init_rcon_logger

    init_task = asyncio.create_task(init_rcon_logger())
    await dp.start_polling(bot)
    await init_task  # Чтобы не завершаться раньше

if __name__ == "__main__":
    asyncio.run(full_main())