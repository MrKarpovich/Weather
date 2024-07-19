import requests
import datetime
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

# Создание или обновление таблицы users
cur.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE,
                city TEXT)""")
conn.commit()

# Добавление новых столбцов, если они не существуют
cur.execute("PRAGMA table_info(users)")
columns = [column[1] for column in cur.fetchall()]

if 'last_alert_time_lvl_2' not in columns:
    cur.execute("ALTER TABLE users ADD COLUMN last_alert_time_lvl_2 TEXT")
if 'last_alert_time_lvl_3' not in columns:
    cur.execute("ALTER TABLE users ADD COLUMN last_alert_time_lvl_3 TEXT")
if 'last_alert_time_lvl_4' not in columns:
    cur.execute("ALTER TABLE users ADD COLUMN last_alert_time_lvl_4 TEXT")
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
        "lvl_4": "🟥 ВНИМАНИЕ!!! Экстремальная погода, которая обязательно нанесет ущерб здоровью!!! НЕМЕДЛЕННО предпринять меры: найти укрытие вдали от деревьев и летающих предметов!"
    }
    if (pop > 0 and wind > 20) or temp < -40 or (temp > 40 and humidity > 40):
        return danger_levels["lvl_4"]
    elif (pop > 0.2 and wind > 15) or (temp > 33 and humidity > 50):
        return danger_levels["lvl_3"]
    elif (pop > 0.4 and wind > 9) or (temp > 30 and humidity > 50):
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
    return speed * 3.6  # Конвертация м/с -> км/ч


def get_sun_times(sunrise, sunset):
    sunrise_time = datetime.datetime.fromtimestamp(sunrise).strftime('%H:%M')
    sunset_time = datetime.datetime.fromtimestamp(sunset).strftime('%H:%M')
    return sunrise_time, sunset_time


def get_day_length(sunrise, sunset):
    day_length_seconds = sunset - sunrise
    hours, remainder = divmod(day_length_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}ч {minutes}мин"


async def send_weather_warning(user_id, city, danger_level, weather_details):
    await bot.send_message(user_id, f"⚠️ Обнаружена угроза погоды в {city}!\n"
                                    f"Уровень угрозы: {danger_level}\n"
                                    f"Температура: {weather_details['temp']}°C\n"
                                    f"Влажность: {weather_details['humidity']}%\n"
                                    f"Ветер: {weather_details['wind_speed']} м/с ({weather_details['wind_speed_km_h']:.2f} км/ч)\n"
                                    f"Давление: {weather_details['pressure']} гПа\n"
                                    f"Вероятность осадков: {weather_details['pop'] * 100}%\n"
                                    f"Восход: {weather_details['sunrise_time']}\n"
                                    f"Закат: {weather_details['sunset_time']}\n"
                                    f"Продолжительность дня: {weather_details['day_length']}")


async def check_weather():
    clean_database()  # Очистка базы данных перед проверкой погоды

    cur.execute("SELECT user_id, city, last_alert_time_lvl_2, last_alert_time_lvl_3, last_alert_time_lvl_4 FROM users")
    users = cur.fetchall()

    for user_id, city, last_alert_time_lvl_2, last_alert_time_lvl_3, last_alert_time_lvl_4 in users:
        try:
            weather_data = get_weather_data(city)
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

            weather_details = {
                "temp": cur_weather,
                "humidity": humidity,
                "wind_speed": wind_speed_m_s,
                "wind_speed_km_h": wind_speed_km_h,
                "pressure": pressure,
                "pop": pop,
                "sunrise_time": sunrise_time,
                "sunset_time": sunset_time,
                "day_length": day_length
            }

            current_time = datetime.datetime.now()

            if danger_level == "🟨 Неблагоприятная погода, которая может нарушить планы на день.":
                if not last_alert_time_lvl_2 or (
                        current_time - datetime.datetime.fromisoformat(last_alert_time_lvl_2)).total_seconds() > 43200:
                    await send_weather_warning(user_id, city, danger_level, weather_details)
                    cur.execute("UPDATE users SET last_alert_time_lvl_2 = ? WHERE user_id = ?",
                                (current_time.isoformat(), user_id))
                    conn.commit()

            elif danger_level == "🟧 Опасная погода, которая может нанести ущерб здоровью, привести к экономическим потерям и тратам.":
                if not last_alert_time_lvl_3 or (
                        current_time - datetime.datetime.fromisoformat(last_alert_time_lvl_3)).total_seconds() > 14400:
                    await send_weather_warning(user_id, city, danger_level, weather_details)
                    cur.execute("UPDATE users SET last_alert_time_lvl_3 = ? WHERE user_id = ?",
                                (current_time.isoformat(), user_id))
                    conn.commit()

            elif danger_level == "🟥 ВНИМАНИЕ!!! Экстремальная погода, которая обязательно нанесет ущерб здоровью и приведет к большим экономическим потерям! НЕМЕДЛЕННО предпринять меры: найти укрытие вдали от деревьев и летающих предметов!":
                if not last_alert_time_lvl_4 or (
                        current_time - datetime.datetime.fromisoformat(last_alert_time_lvl_4)).total_seconds() > 1800:
                    await send_weather_warning(user_id, city, danger_level, weather_details)
                    cur.execute("UPDATE users SET last_alert_time_lvl_4 = ? WHERE user_id = ?",
                                (current_time.isoformat(), user_id))
                    conn.commit()

        except BotBlocked:
            cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
        except Exception as e:
            print(f"Ошибка при проверке погоды для {city}: {e}")


# Настройка планировщика
scheduler = AsyncIOScheduler()
scheduler.add_job(check_weather, "interval", seconds=10)
scheduler.start()

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
