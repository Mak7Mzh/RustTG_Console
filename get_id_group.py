from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from cfg import TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=["start"])
async def get_group_id(message: types.Message):
    chat_id = message.chat.id
    chat_title = message.chat.title if message.chat.title else "ЛС"
    await message.reply(f"chat_id: {chat_id}\nНазвание: {chat_title}")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
