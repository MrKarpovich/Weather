import requests
import datetime
import time
import sqlite3
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.utils.exceptions import BotBlocked
from apscheduler.schedulers.asyncio import AsyncIOScheduler

tg_bot_token = "-"
open_weather_token = "-"

bot = Bot(token=tg_bot_token)
dp = Dispatcher(bot)

# Создание или подключение к базе данных SQLite
conn = sqlite3.connect('weather_bot.db')
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE,
                city TEXT)""")
conn.commit()


@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.reply(
        "Привет! Напиши мне город, а я буду следить за погодой и предупреждать тебя о потенциальных угрозах.")


@dp.message_handler()
async def add_or_update_city(message: types.Message):
    user_id = message.from_user.id
    city = message.text.strip()

    # Добавление или обновление города пользователя
    cur.execute("REPLACE INTO users (user_id, city) VALUES (?, ?)", (user_id, city))
    conn.commit()

    await message.reply(f"Город {city} был добавлен/обновлен. Теперь я буду следить за погодой в этом городе.")


def get_weather_data(city):
    try:
        response = requests.get(
            f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={open_weather_token}&units=metric"
        )
        return response.json()
    except Exception as e:
        raise Exception(f"Ошибка получения данных о погоде: {e}")


def get_forecast_data(city):
    try:
        response = requests.get(
            f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={open_weather_token}&units=metric"
        )
        return response.json()
    except Exception as e:
        raise Exception(f"Ошибка получения данных о прогнозе: {e}")


def get_danger_level(temp, wind, pop, humidity):
    danger_levels = {
        "lvl_1": "🟩 Опасности нет, консультативная информация.",
        "lvl_2": "🟨 Неблагоприятная погода, которая может нарушить планы на день.",
        "lvl_3": "🟧 Опасная погода, которая может нанести ущерб здоровью, привести к экономическим потерям и тратам.",
        "lvl_4": "🟥 ВНИМАНИЕ!!! Экстремальная погода, которая обязательно нанесет ущерб здоровью и приведет к большим экономическим потерям! НЕМЕДЛЕННО предпринять меры: найти укрытие вдали от деревьев и летающих предметов!"
    }
    if (pop > 0.5 and wind > 20) or temp < -40 or (temp > 40 and humidity > 40):
        return danger_levels["lvl_4"]
    elif (pop > 0.5 and wind > 15) or (temp > 33 and humidity > 50):
        return danger_levels["lvl_3"]
    elif (pop > 0 and wind > 9) or (temp > 25 and humidity > 30):
        return danger_levels["lvl_2"]
    else:
        return danger_levels["lvl_1"]


def clean_database():
    cur.execute("""
        DELETE FROM users
        WHERE id NOT IN (
            SELECT MAX(id) FROM users GROUP BY user_id
        )
    """)
    conn.commit()


def convert_wind_speed(speed):
    return speed * 3.6  # Конвертация м/с в км/ч


def get_sun_times(sunrise, sunset):
    sunrise_time = datetime.datetime.fromtimestamp(sunrise).strftime('%H:%M')
    sunset_time = datetime.datetime.fromtimestamp(sunset).strftime('%H:%M')
    return sunrise_time, sunset_time


def get_day_length(sunrise, sunset):
    day_length_seconds = sunset - sunrise
    hours, remainder = divmod(day_length_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}ч {minutes}мин"


async def check_weather():
    clean_database()  # Очистка базы данных перед проверкой погоды

    cur.execute("SELECT user_id, city FROM users")
    users = cur.fetchall()

    for user_id, city in users:
        try:
            weather_data = get_weather_data(city)
            forecast_data = get_forecast_data(city)

            # Анализ текущей погоды
            cur_weather = weather_data["main"]["temp"]
            humidity = weather_data["main"]["humidity"]
            wind_speed_m_s = weather_data["wind"]["speed"]
            wind_speed_km_h = convert_wind_speed(wind_speed_m_s)
            pressure = weather_data["main"]["pressure"]
            pop = weather_data.get('pop', 0)  # Вероятность осадков может отсутствовать
            sunrise = weather_data["sys"]["sunrise"]
            sunset = weather_data["sys"]["sunset"]
            sunrise_time, sunset_time = get_sun_times(sunrise, sunset)
            day_length = get_day_length(sunrise, sunset)
            danger_level = get_danger_level(cur_weather, wind_speed_m_s, pop, humidity)

            if danger_level != "🟩 Опасности нет, консультативная информация.":
                await bot.send_message(user_id, f"⚠️ Обнаружена угроза погоды в {city}!\n"
                                                f"Уровень угрозы: {danger_level}\n"
                                                f"Температура: {cur_weather}°C\n"
                                                f"Влажность: {humidity}%\n"
                                                f"Ветер: {wind_speed_m_s} м/с ({wind_speed_km_h:.2f} км/ч)\n"
                                                f"Давление: {pressure} гПа\n"
                                                f"Вероятность осадков: {pop * 100}%\n"
                                                f"Восход: {sunrise_time}\n"
                                                f"Закат: {sunset_time}\n"
                                                f"Продолжительность дня: {day_length}")

            # Анализ погоды на завтра
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            tomorrow_weather = None
            for item in forecast_data['list']:
                date = datetime.datetime.fromtimestamp(item['dt'])
                if date.date() == tomorrow:
                    tomorrow_weather = item
                    break
            if tomorrow_weather:
                tomorrow_temp = tomorrow_weather['main']['temp']
                tomorrow_humidity = tomorrow_weather['main']['humidity']
                tomorrow_wind_speed_m_s = tomorrow_weather['wind']['speed']
                tomorrow_wind_speed_km_h = convert_wind_speed(tomorrow_wind_speed_m_s)
                tomorrow_pressure = tomorrow_weather['main']['pressure']
                tomorrow_pop = tomorrow_weather.get('pop', 0)
                tomorrow_danger_level = get_danger_level(tomorrow_temp, tomorrow_wind_speed_m_s, tomorrow_pop,
                                                         tomorrow_humidity)
                if tomorrow_danger_level != "🟩 Опасности нет, консультативная информация.":
                    await bot.send_message(user_id, f"⚠️ Обнаружена угроза погоды в {city} на завтра!\n"
                                                    f"Уровень угрозы: {tomorrow_danger_level}\n"
                                                    f"Температура: {tomorrow_temp}°C\n"
                                                    f"Влажность: {tomorrow_humidity}%\n"
                                                    f"Ветер: {tomorrow_wind_speed_m_s} м/с ({tomorrow_wind_speed_km_h:.2f} км/ч)\n"
                                                    f"Давление: {tomorrow_pressure} гПа\n"
                                                    f"Вероятность осадков: {tomorrow_pop * 100}%")

            # Анализ погоды на послезавтра
            after_tomorrow = datetime.date.today() + datetime.timedelta(days=2)
            after_tomorrow_weather = None
            for item in forecast_data['list']:
                date = datetime.datetime.fromtimestamp(item['dt'])
                if date.date() == after_tomorrow:
                    after_tomorrow_weather = item
                    break
            if after_tomorrow_weather:
                after_tomorrow_temp = after_tomorrow_weather['main']['temp']
                after_tomorrow_humidity = after_tomorrow_weather['main']['humidity']
                after_tomorrow_wind_speed_m_s = after_tomorrow_weather['wind']['speed']
                after_tomorrow_wind_speed_km_h = convert_wind_speed(after_tomorrow_wind_speed_m_s)
                after_tomorrow_pressure = after_tomorrow_weather['main']['pressure']
                after_tomorrow_pop = after_tomorrow_weather.get('pop', 0)
                after_tomorrow_danger_level = get_danger_level(after_tomorrow_temp, after_tomorrow_wind_speed_m_s,
                                                               after_tomorrow_pop, after_tomorrow_humidity)
                if after_tomorrow_danger_level != "🟩 Опасности нет, консультативная информация.":
                    await bot.send_message(user_id, f"⚠️ Обнаружена угроза погоды в {city} на послезавтра!\n"
                                                    f"Уровень угрозы: {after_tomorrow_danger_level}\n"
                                                    f"Температура: {after_tomorrow_temp}°C\n"
                                                    f"Влажность: {after_tomorrow_humidity}%\n"
                                                    f"Ветер: {after_tomorrow_wind_speed_m_s} м/с ({after_tomorrow_wind_speed_km_h:.2f} км/ч)\n"
                                                    f"Давление: {after_tomorrow_pressure} гПа\n"
                                                    f"Вероятность осадков: {after_tomorrow_pop * 100}%")

        except BotBlocked:
            # Пользователь заблокировал бота, удаляем из базы данных
            cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
        except Exception as e:
            print(f"Не удалось проверить погоду для пользователя {user_id} в городе {city}: {e}")


async def on_startup(_):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_weather, "interval", seconds=10)
    scheduler.start()


async def on_shutdown(dp):
    await bot.close()
    await dp.storage.close()
    conn.close()


if __name__ == '__main__':
    try:
        executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)
    except Exception as e:
        print(f"Бот крашнул с ошибкой: {e}")
        time.sleep(5)  # Подождать 5 секунд перед повторным запуском
