import requests
import datetime
import time
import os
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

tg_bot_token = os.getenv("TG_BOT_TOKEN")
open_weather_token = os.getenv("OPEN_WEATHER_TOKEN")
bot = Bot(token=tg_bot_token)
dp = Dispatcher(bot)

print(f"Бот запустился, проверяйте телегу")

@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.reply("Привет! Напиши мне город, а я отвечу какая там прямо сейчас погода")

@dp.message_handler()
async def get_weather(message: types.Message):
    code_to_smile = {
        "Clear": "Ясно \U00002600",
        "Clouds": "Облачно \U00002601",
        "Rain": "Дождь \U00002614",
        "Drizzle": "Слабый Дождь \U00002614",
        "Thunderstorm": "Гроза \U000026A1",
        "Snow": "Снег \U0001F328",
        "Mist": "Туман \U0001F32B"
    }

    danger_levels = {
        "🟩": "🟩 Опасности нет, консультативная информация.",
        "🟨": "🟨 Неблагоприятная погода, которая может нарушить планы на день.",
        "🟧": "🟧 Опасная погода, которая может нанести ущерб здоровью, привести к экономическим потерям и тратам.",
        "🟥": "🟥 ВНИМАНИЕ!!! Экстремальная погода, которая обязательно нанесет ущерб здоровью и приведет к большим экономическим потерям! НЕМЕДЛЕННО предпринять меры: найти укрытие вдали от деревьев и летающих предметов!"
    }

    try:
        r = requests.get(
            f"http://api.openweathermap.org/data/2.5/weather?q={message.text}&appid={open_weather_token}&units=metric"
        )
        data = r.json()

        city = data["name"]
        cur_weather = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        pressure = data["main"]["pressure"]
        wind = data["wind"]["speed"]
        sunrise_timestamp = datetime.datetime.fromtimestamp(data["sys"]["sunrise"])
        sunset_timestamp = datetime.datetime.fromtimestamp(data["sys"]["sunset"])
        length_of_the_day = sunset_timestamp - sunrise_timestamp

        weather_description = data["weather"][0]["main"]
        if weather_description in code_to_smile:
            wd = code_to_smile[weather_description]
        else:
            wd = "Глянь в окно =)"

        def get_danger_level(temp, wind, pop, humidity):
            if (pop > 0.5 and wind > 20) or temp < -40 or (temp > 40 and humidity > 40):
                return danger_levels["🟥"]
            elif (pop > 0.5 and wind > 15) or (temp > 33 and humidity > 50):
                return danger_levels["🟧"]
            elif (pop > 0 and wind > 9) or (temp > 25 and humidity > 30):
                return danger_levels["🟨"]
            else:
                return danger_levels["🟩"]

        # Определяем уровень опасности для текущей погоды
        current_danger_level = get_danger_level(cur_weather, wind, data.get('pop', 0), humidity)

        # Получаем прогноз на завтра
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        tomorrow_response = requests.get(
            f"http://api.openweathermap.org/data/2.5/forecast?q={message.text}&appid={open_weather_token}&units=metric"
        )
        tomorrow_data = tomorrow_response.json()
        tomorrow_weather = None
        for item in tomorrow_data['list']:
            date = datetime.datetime.fromtimestamp(item['dt'])
            if date.date() == tomorrow:
                tomorrow_weather = item
                break

        # Получаем прогноз на послезавтра
        after_tomorrow = datetime.date.today() + datetime.timedelta(days=2)
        after_tomorrow_response = requests.get(
            f"http://api.openweathermap.org/data/2.5/forecast?q={message.text}&appid={open_weather_token}&units=metric"
        )
        after_tomorrow_data = after_tomorrow_response.json()
        after_tomorrow_weather = None
        for item in after_tomorrow_data['list']:
            date = datetime.datetime.fromtimestamp(item['dt'])
            if date.date() == after_tomorrow:
                after_tomorrow_weather = item
                break

        await message.reply(f"Запрос погоды был сделан: {datetime.datetime.now().strftime('%d.%m.%y %H:%M')}\n"
                            f"====== Погода в {city} ====== \n"
                            f"Текущая погода: {cur_weather}C° {wd}\n"
                            f"Влажность: {humidity}%\n"
                            f"Давление: {pressure} мм.рт.ст\n"
                            f"Ветер: {wind} м/с - это {round(wind * 3.6)} км/ч\n"
                            f"Восход: {sunrise_timestamp}\n"
                            f"Закат: {sunset_timestamp}\n"
                            f"Продолжительность дня: {length_of_the_day}\n"
                            f"Уровень опасности: {current_danger_level}\n"
                            f"====== Прогноз на завтра ====== \n"
                            f"Температура: {tomorrow_weather['main']['temp']}C° {code_to_smile[tomorrow_weather['weather'][0]['main']]}\n"
                            f"Влажность: {tomorrow_weather['main']['humidity']}%\n"
                            f"Давление: {tomorrow_weather['main']['pressure']} мм.рт.ст\n"
                            f"Ветер: {tomorrow_weather['wind']['speed']} м/с - это {round(tomorrow_weather['wind']['speed'] * 3.6)} км/ч\n"
                            f"Вероятность выпадения осадков: {tomorrow_weather['pop'] * 100}%\n"
                            f"Уровень опасности: {get_danger_level(tomorrow_weather['main']['temp'], tomorrow_weather['wind']['speed'], tomorrow_weather['pop'], tomorrow_weather['main']['humidity'])}\n"
                            f"====== Прогноз на послезавтра ====== \n"
                            f"Температура: {after_tomorrow_weather['main']['temp']}C° {code_to_smile[after_tomorrow_weather['weather'][0]['main']]}\n"
                            f"Влажность: {after_tomorrow_weather['main']['humidity']}%\n"
                            f"Давление: {after_tomorrow_weather['main']['pressure']} мм.рт.ст\n"
                            f"Ветер: {after_tomorrow_weather['wind']['speed']} м/с - это {round(after_tomorrow_weather['wind']['speed'] * 3.6)} км/ч\n"
                            f"Вероятность осадков: {after_tomorrow_weather['pop'] * 100}%\n"
                            f"Уровень опасности: {get_danger_level(after_tomorrow_weather['main']['temp'], after_tomorrow_weather['wind']['speed'], after_tomorrow_weather['pop'], after_tomorrow_weather['main']['humidity'])}\n"
                            )

    except Exception as e:
        await message.reply(f"Проверьте название города. Ошибка: {e}")

async def on_shutdown(dp):
    await bot.close()
    await dp.storage.close()

if __name__ == '__main__':
    try:
        executor.start_polling(dp, on_shutdown=on_shutdown)
    except Exception as e:
        print(f"Бот крашнул с ошибкой: {e}")
        time.sleep(5)  # Подождать 5 секунд перед повторным запуском
