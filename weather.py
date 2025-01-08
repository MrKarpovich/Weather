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

tg_bot_token = "-"
open_weather_token = "-"

DANGER_1 = "🟩 Опасности нет, консультативная информация."
DANGER_2 = "🟨\n⚠️Я объявляю жёлтый уровень тревоги!"
DANGER_3 = "🟧 🟧 ВНИМАНИЕ!!! 🟧 🟧 \n\n     ⚠️⚠️⚠️Опасная погода! ⚠️⚠️⚠️\n\nОжидается ОЧЕНЬ сильный ветер, который принесет значительный ущерб. ИЗБЕГАЙТЕ ДАВКИ!\n Возможны травмы от падающих деревьев, повреждения зданий, автомобилей и другой собственности, возникнут перебои в подаче электроэнергии и сбои в транспортном движении.\n\n ЧТО ДЕЛАТЬ?! СОВЕТЫ ПО БЕЗОПАСНОСТИ!\n\n НЕМЕДЛЕННО Держаться подальше ОТ деревьев, рекламных щитов и любых других объектов, которые могут снести ветром.\n Закрепите все свои предметы, которые могут быть унесены ветром.\n ПРИ ВОЗМОЖНОСТИ Оставайтесь внутри зданий (где безопасно) и избегайте ненужных поездок.\n ИЗБЕГАЙТЕ ДАВКИ! Думайте своей головой, а не толпой!\n\nБерегите себя и своих близких!\n"
DANGER_4 = "🟥🟥🟥🟥🟥🟥🟥🟥 \n\n⚠️⚠️⚠️ **ТРЕВОГА!!! ВНИМАНИЕ!!!** ⚠️⚠️⚠️\n\n**Экстремальная погода!! Немедленно найдите укрытие! Торнадо может нанести серьёзный ущерб здоровью и привести к значительным экономическим потерям!\n\nНЕМЕДЛЕННО предпринять меры:\nНайдите укрытие вдали от деревьев, рекламных щитов и любых других объектов, которые могут быть унесены ветром.\nЗакройте окна и двери.\nОставайтесь в безопасных помещениях, таких как подвалы или внутренние комнаты без окон.\nИзбегайте перемещений на улице и не стоите близко к стеклянным и металлическим конструкциям.\n\n**ПОВТОРЯЮ!!! НЕМЕДЛЕННО НАЙДИТЕ УБЕЖИЩЕ!**\n\n**ИЗБЕГАЙТЕ ДАВКИ!** \n\nБерегите себя и своих близких!"

condition_emojis = {
    # Группа 2xx: Гроза
    '200': '⚡ Гроза с небольшим дождём',
    '201': '⚡⚡ Гроза с дождем',
    '202': '⚡⚡⚡ Гроза с сильным дождем',
    '210': '🌩️ Небольшая гроза',
    '211': '🌩️⚡ Гроза',
    '212': '🌩️🌩️ Сильная гроза',
    '221': '🌩️⚡🌩️ Рваная гроза',
    '230': '⚡💧 Гроза с небольшим моросящим дождем',
    '231': '⚡💧💦 Гроза с моросью',
    '232': '⚡💧💦💧 Гроза с сильным моросящим дождем',

    # Группа 3xx: Морось
    '300': '🌧️ Морось слабой интенсивности',
    '301': '🌧️💧 Морось',
    '302': '🌧️💧💧 Сильный моросящий дождь',
    '310': '🌧️💧🌧️ Слабый моросящий дождь',
    '311': '🌧️🌧️ Моросящий дождь',
    '312': '🌧️🌧️🌧️ Сильный интенсивный моросящий дождь',
    '313': '🌧️🌧️💧 Ливневый дождь и морось',
    '314': '🌧️🌧️🌧️ Сильный ливневый дождь и морось',

    # Группа 5xx: Дождь
    '500': '🌦️ Небольшой дождь',
    '501': '🌧️ Умеренный дождь',
    '502': '🌧️🌧️ Сильный ливень',
    '503': '🌧️🌧️🌧️ Очень сильный дождь',
    '504': '🌧️🌧️🌧️🌧️ Сильный дождь',
    '511': '🌨️❄️ Ледяной дождь',
    '520': '🌧️💧 Слабый ливень',
    '521': '🌧️🌧️ Ливень',
    '522': '🌧️🌧️🌧️ Сильный ливневый дождь',
    '531': '🌧️🌧️🌧️🌧️ Рваный ливневый дождь',

    # Группа 6xx: Снег
    '600': '❄ Небольшой снег',
    '601': '❄️❄Снег',
    '602': '❄️❄️❄Сильный снегопад',
    '611': '🌨️❄️ Мокрый снег',
    '612': '🌨️💧❄️ Небольшой ливень со снегом',
    '613': '🌨️❄️💧 Ливень со снегом',
    '615': '❄️💧❄️ Небольшой дождь со снегом',
    '616': '🌨️❄️ Дождь и снег',
    '620': '❄️🌨️❄️ Небольшой ливневый снег',
    '621': '❄️❄️🌨️ Ливневый снег',
    '622': '❄️❄️❄️🌨️ Сильный ливневый снег',

    # Группа 7xx: Атмосфера
    '701': '🌫️ Туман',
    '711': '💨 Дым',
    '721': '🌫️ Туман',
    '731': '🌵 Песок',
    '741': '🌫️ Туман',
    '751': '🌵 Песок',
    '761': '💨 Пыль',
    '762': '💨 Пепел',
    '771': '🌀 Шквал',
    '781': '🌪️ Торнадо',

    # Группа 800: Очистка
    '800': '🌞 Ясное небо <10%',

    # Группа 80x: Облака
    '801': '🌤️ Небольшая облачность 11-25%',
    '802': '⛅ Рассеянная облачность 25-50%',
    '803': '🌥️ Разорванная облачность 51-84%',
    '804': '☁ Облачность 85-100%',
}


bot = Bot(token=tg_bot_token, timeout=120)
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
        # Проверка, существует ли запись с таким user_id
        cur.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        existing_user = cur.fetchone()

        if existing_user:
            # Обновление города и очистка времен для уровня предупреждений
            cur.execute("""
                    UPDATE users
                    SET city = ?, last_alert_time_lvl_2 = NULL, last_alert_time_lvl_3 = NULL, last_alert_time_lvl_4 = NULL
                    WHERE user_id = ?
                """, (city, user_id))
        else:
            # Добавление нового пользователя с очисткой времен предупреждений
            cur.execute("""
                    INSERT INTO users (user_id, city, last_alert_time_lvl_2, last_alert_time_lvl_3, last_alert_time_lvl_4)
                    VALUES (?, ?, NULL, NULL, NULL)
                """, (user_id, city))

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
    except requests.exceptions.RequestException as error_validate_city:
        # Записываем ошибку при запросе
        print(f"Ошибка запроса validate_city: {error_validate_city}")
        return False
    except Exception as error_validate_city:
        # Записываем другие исключения
        print(f"Неизвестная ошибка validate_city: {error_validate_city}")
        return False


# Это глянуть погоду в текущую секунду, что не надо
# def get_weather_data(city):
#     try:
#         response = requests.get(
#             f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={open_weather_token}&units=metric"
#         )
#         return response.json()
#     except Exception as e:
#         raise Exception(f"Ошибка получения данных о погоде: {e}")


def get_forecast_data(city):
    try:
        response = requests.get(
            f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={open_weather_token}&units=metric"
        )
        return response.json()
    except Exception as error_get_forecast_data:
        print(f"Ошибка при получении прогноза в get_forecast_data: {error_get_forecast_data}")


def get_danger_level(temp, wind, pop, humidity, weather_conditions):
    danger_levels = {
        "lvl_1": DANGER_1,
        "lvl_2": DANGER_2,
        "lvl_3": DANGER_3,
        "lvl_4": DANGER_4
    }

    # Проверка на наличие опасных погодных условий
    hazardous_weather = any(
        200 <= condition['id'] <= 232 or  # Гроза (Thunderstorm)
        condition['id'] in [310, 312, 313, 314] or  # Мелкий дождик (Drizzle)
        502 <= condition['id'] <= 511 or  # Дождь (Rain)
        condition['id'] in [521, 522, 531] or
        602 <= condition['id'] <= 622 or  # Снег (Snow)
        701 <= condition['id'] <= 781  # Атмосферные условия (Mist, Fog, Smoke, Dust, Squall, Tornado)
        for condition in weather_conditions
    )

    if wind > 20:
        return danger_levels["lvl_4"]
    elif wind > 15:
        return danger_levels["lvl_3"]
    elif wind > 9 or (temp > 31 and humidity > 80) or hazardous_weather:
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
    return speed * 3.6  # Конвертация м/с --> км/ч


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
    # Для каждого погодного условия в прогнозе
    for condition in weather_details["weather_conditions"]:
        condition_code = str(condition['id'])  # Получаем код погодного условия как строку
        # Получаем описание погодного условия, если оно есть в condition_emojis
        description = condition_emojis.get(condition_code, 'Неизвестное условие')

        hazardous_conditions.append(f"{description}")  # Добавляем описание в список опасных условий

    # Если опасные условия найдены, отображаем их в сообщении
    hazardous_conditions_text = '\n'.join(hazardous_conditions) if hazardous_conditions else "_________________________"

    await bot.send_message(user_id, f"⚠️Обнаружена угроза погоды \n на {forecast_time} в городе {city}!\n"
                                    f"🚨 Уровень угрозы: {danger_level}\n"
                                    f"🌡️ Температура: {weather_details['temp']}°C\n"
                                    f"💧 Влажность: {weather_details['humidity']}%\n"
                                    f"💨 Ветер: {weather_details['wind_speed']} м/с ({weather_details['wind_speed_km_h']:.2f} км/ч)\n"
                                    f"🧭 Давление: {weather_details['pressure']} гПа\n"
                                    f"🌧❓️ Вероятность осадков: {weather_details['pop'] * 100}%\n"
                                    f"Обратите внимание на погодные условия:\n{hazardous_conditions_text}")



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
            # weather_data = get_weather_data(city)
            forecast_data = get_forecast_data(city)

            forecast_by_day = get_forecast_for_next_days(forecast_data)

            for day, forecasts in forecast_by_day.items():
                for forecast_time_str, forecast_entry in forecasts:
                    weather_details = get_weather_details_from_forecast(forecast_entry)
                    danger_level = get_danger_level(weather_details["temp"], weather_details["wind_speed"], weather_details["pop"], weather_details["humidity"], weather_details["weather_conditions"])

                    current_time = datetime.datetime.now()

                    if danger_level == DANGER_2:
                        if not last_alert_time_lvl_2 or (current_time - datetime.datetime.fromisoformat(last_alert_time_lvl_2)).total_seconds() > 54000:
                            await send_weather_warning(user_id, city, danger_level, weather_details, forecast_time_str)
                            cur.execute("UPDATE users SET last_alert_time_lvl_2 = ? WHERE user_id = ?", (current_time.isoformat(), user_id))
                            conn.commit()

                    elif danger_level == DANGER_3:
                        if not last_alert_time_lvl_3 or (current_time - datetime.datetime.fromisoformat(last_alert_time_lvl_3)).total_seconds() > 28800:
                            await send_weather_warning(user_id, city, danger_level, weather_details, forecast_time_str)
                            cur.execute("UPDATE users SET last_alert_time_lvl_3 = ? WHERE user_id = ?", (current_time.isoformat(), user_id))
                            conn.commit()

                    elif danger_level == DANGER_4:
                        if not last_alert_time_lvl_4 or (current_time - datetime.datetime.fromisoformat(last_alert_time_lvl_4)).total_seconds() > 3600:
                            await send_weather_warning(user_id, city, danger_level, weather_details, forecast_time_str)
                            cur.execute("UPDATE users SET last_alert_time_lvl_4 = ? WHERE user_id = ?", (current_time.isoformat(), user_id))
                            conn.commit()

        except BotBlocked:
            cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
        except Exception as error_check_weather:
            print(f"Ошибка при проверке погоды для {city}: {error_check_weather}")


# Настройка планировщика
scheduler = AsyncIOScheduler()
scheduler.add_job(check_weather, "interval", seconds=120)
scheduler.start()

if __name__ == '__main__':
    try:
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        print(f"Бот с ошибкой: {e}")
        time.sleep(5)  # Подождать 5 секунд перед повторным запуском
