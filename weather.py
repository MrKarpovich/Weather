import requests
import datetime
import time
import sqlite3
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.utils.exceptions import BotBlocked
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

tg_bot_token = "tg_bot_token"
open_weather_token = "open_weather_token"

DANGER_1 = "🟩 Опасности нет, консультативная информация."
DANGER_2 = "🟨 \n⚠️Обнаружены сильные порывы ветра!"
DANGER_3 = "🟧 🟧 ВНИМАНИЕ! 🟧 🟧 \n⚠️Опасная погода! Очень сильный ветер, который может нанести ущерб здоровью, привести к экономическим потерям и тратам!"
DANGER_4 = "🟥🟥🟥 ВНИМАНИЕ!!!🟥🟥🟥 \n⚠️Экстремальная погода! Срочно найти убежище! Погода обязательно нанесет ущерб здоровью и приведет к большим экономическим потерям! НЕМЕДЛЕННО предпринять меры: найти укрытие вдали от деревьев и летающих предметов! ПОВТОРЯЮ! НЕМЕДЛЕННО НАЙТИ УБЕЖИЩЕ!"

bot = Bot(token=tg_bot_token)
dp = Dispatcher(bot)

# Создание или подключение к базе данных SQLite
conn = sqlite3.connect('weather_bot.db')
cur = conn.cursor()

# Создание или обновление таблицы users
cur.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE,
                city TEXT,
                last_alert_time_lvl_2 TEXT,
                last_alert_time_lvl_3 TEXT,
                last_alert_time_lvl_4 TEXT)""")
conn.commit()


@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.reply(
        "Привет! Напиши мне город, а я буду следить за погодой и предупреждать тебя о потенциальных угрозах.")


@dp.message_handler()
async def add_or_update_city(message: types.Message):
    user_id = message.from_user.id
    city = message.text.strip()

    if validate_city(city):
        # Добавление или обновление города пользователя
        cur.execute("REPLACE INTO users (user_id, city) VALUES (?, ?)", (user_id, city))
        conn.commit()
        await message.reply(f"Город {city} был добавлен/обновлен. Теперь я буду следить за погодой в этом городе.")
    else:
        await message.reply(f"Город {city} не найден. Пожалуйста, проверьте правильность написания.")


def validate_city(city):
    try:
        response = requests.get(
            f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={open_weather_token}"
        )
        data = response.json()
        return data.get("cod") == 200
    except Exception as e:
        return False


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


def get_danger_level(temp, wind, pop, humidity, weather_conditions):
    danger_levels = {
        "lvl_1": DANGER_1,
        "lvl_2": DANGER_2,
        "lvl_3": DANGER_3,
        "lvl_4": DANGER_4
    }

    # Проверка на наличие опасных погодных условий
    hazardous_weather = any(
        condition['main'] in ['Thunderstorm', 'Hail'] or 'heavy' in condition['description'].lower()
        for condition in weather_conditions
    )

    if wind > 20:
        return danger_levels["lvl_4"]
    elif wind > 15 or (temp > 35 and humidity > 80):
        return danger_levels["lvl_3"]
    elif wind > 9 or hazardous_weather:
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


def get_forecast_for_next_days(forecast_data):
    tz = pytz.timezone('UTC')  # Замените на часовой пояс вашего города, если нужно
    now = datetime.datetime.now(tz)
    today = now.date()
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)

    forecast_by_day = {
        'Сегодня': [],
        'Завтра': [],
        'Послезавтра': []
    }

    for entry in forecast_data["list"]:
        forecast_time = datetime.datetime.fromtimestamp(entry["dt"], tz)
        forecast_date = forecast_time.date()
        forecast_time_str = forecast_time.strftime('%d.%m.%Y %H:%M')

        if forecast_date == today:
            forecast_by_day['Сегодня'].append((forecast_time_str, entry))
        elif forecast_date == tomorrow:
            forecast_by_day['Завтра'].append((forecast_time_str, entry))
        elif forecast_date == day_after_tomorrow:
            forecast_by_day['Послезавтра'].append((forecast_time_str, entry))

    return forecast_by_day


async def send_weather_warning(user_id, city, danger_level, weather_details, forecast_time):
    hazardous_conditions = []
    for condition in weather_details["weather_conditions"]:
        if condition['main'] in ['Thunderstorm', 'Hail', 'Snow'] or 'heavy' in condition['description'].lower():
            hazardous_conditions.append(condition['description'])

    hazardous_conditions_text = '\n'.join(hazardous_conditions) if hazardous_conditions else "_________________________"

    await bot.send_message(user_id, f"⚠️Обнаружена угроза погоды на {forecast_time} в городе {city}!\n"
                                    f"Уровень угрозы: {danger_level}\n"
                                    f"Температура: {weather_details['temp']}°C\n"
                                    f"Влажность: {weather_details['humidity']}%\n"
                                    f"Ветер: {weather_details['wind_speed']} м/с ({weather_details['wind_speed_km_h']:.2f} км/ч)\n"
                                    f"Давление: {weather_details['pressure']} гПа\n"
                                    f"Вероятность осадков: {weather_details['pop'] * 100}%\n"
                                    f"\n{hazardous_conditions_text}")


def get_weather_details_from_forecast(forecast_entry):
    temp = forecast_entry["main"]["temp"]
    humidity = forecast_entry["main"]["humidity"]
    wind_speed_m_s = forecast_entry["wind"]["speed"]
    wind_speed_km_h = convert_wind_speed(wind_speed_m_s)
    pressure = forecast_entry["main"]["pressure"]
    pop = forecast_entry.get('pop', 0)  # Вероятность осадков может отсутствовать
    weather_conditions = forecast_entry.get("weather", [])
    return {
        "temp": temp,
        "humidity": humidity,
        "wind_speed": wind_speed_m_s,
        "wind_speed_km_h": wind_speed_km_h,
        "pressure": pressure,
        "pop": pop,
        "weather_conditions": weather_conditions
    }


async def check_weather():
    clean_database()

    cur.execute("SELECT user_id, city, last_alert_time_lvl_2, last_alert_time_lvl_3, last_alert_time_lvl_4 FROM users")
    users = cur.fetchall()

    for user_id, city, last_alert_time_lvl_2, last_alert_time_lvl_3, last_alert_time_lvl_4 in users:
        try:
            weather_data = get_weather_data(city)
            forecast_data = get_forecast_data(city)

            forecast_by_day = get_forecast_for_next_days(forecast_data)

            for day, forecasts in forecast_by_day.items():
                for forecast_time_str, forecast_entry in forecasts:
                    weather_details = get_weather_details_from_forecast(forecast_entry)
                    danger_level = get_danger_level(weather_details["temp"], weather_details["wind_speed"], weather_details["pop"], weather_details["humidity"], weather_details["weather_conditions"])

                    current_time = datetime.datetime.now()

                    if danger_level == DANGER_2:
                        if not last_alert_time_lvl_2 or (current_time - datetime.datetime.fromisoformat(last_alert_time_lvl_2)).total_seconds() > 32400:
                            await send_weather_warning(user_id, city, danger_level, weather_details, forecast_time_str)
                            cur.execute("UPDATE users SET last_alert_time_lvl_2 = ? WHERE user_id = ?", (current_time.isoformat(), user_id))
                            conn.commit()

                    elif danger_level == DANGER_3:
                        if not last_alert_time_lvl_3 or (current_time - datetime.datetime.fromisoformat(last_alert_time_lvl_3)).total_seconds() > 14400:
                            await send_weather_warning(user_id, city, danger_level, weather_details, forecast_time_str)
                            cur.execute("UPDATE users SET last_alert_time_lvl_3 = ? WHERE user_id = ?", (current_time.isoformat(), user_id))
                            conn.commit()

                    elif danger_level == DANGER_4:
                        if not last_alert_time_lvl_4 or (current_time - datetime.datetime.fromisoformat(last_alert_time_lvl_4)).total_seconds() > 1800:
                            await send_weather_warning(user_id, city, danger_level, weather_details, forecast_time_str)
                            cur.execute("UPDATE users SET last_alert_time_lvl_4 = ? WHERE user_id = ?", (current_time.isoformat(), user_id))
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

if __name__ == '__main__':
    try:
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        print(f"Бот крашнул с ошибкой: {e}")
        time.sleep(5)  # Подождать 5 секунд перед повторным запуском
