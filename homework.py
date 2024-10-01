import logging
import os
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()


PRACTICUM_TOKEN = os.getenv("TOKEN_PRACT")
TELEGRAM_TOKEN = os.getenv("TOKEN_TELE_BOT")
TELEGRAM_CHAT_ID = os.getenv("TELE_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

logging.basicConfig(
    level=logging.DEBUG,
    filename="sys.stdout",
    format="%(asctime)s, %(levelname)s, %(message)s, %(name)s",
)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.addHandler(handler)


def check_tokens():
    """Проверка наличия токенов."""
    if not PRACTICUM_TOKEN:
        logging.critical(
            "Отсутствие обязательных переменных окружения"
            " во время запуска бота: PRACTICUM_TOKEN"
        )
        raise ValueError("Не указан токен Яндекс.Практикум")
    if not TELEGRAM_TOKEN:
        logging.critical(
            "Отсутствие обязательных переменных окружения"
            " во время запуска бота: TELEGRAM_TOKEN"
        )
        raise ValueError("Не указан токен Телеграм")
    if not TELEGRAM_CHAT_ID:
        logging.critical(
            "Отсутствие обязательных переменных окружения"
            " во время запуска бота: TELEGRAM_CHAT_ID"
        )
        raise ValueError("Не указан ID чата Телеграм")


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logging.debug(f"Сообщение отправлено в Telegram: {message}")


def get_api_answer(timestamp):
    """Получение данных от API."""
    payload = {"from_date": timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=payload
        )
        if homework_statuses.status_code != 200:
            logging.error(
                f"Эндпоинт {ENDPOINT} недоступен."
                f" Код ответа: {homework_statuses.status_code}"
            )
            raise AssertionError(
                f"Эндпоинт {ENDPOINT} недоступен."
                f" Код ответа: {homework_statuses.status_code}"
            )
        logging.debug(f"Ответ от API: {homework_statuses.json()}")
        return homework_statuses.json()
    except requests.RequestException as error:
        logging.error(f"Ошибка при запросе к API: {error}")
        raise RuntimeError(f"Ошибка при запросе к API: {error}")


def check_response(response):
    """Проверка ответа от API."""
    if not isinstance(response, dict):
        logging.error("Ответ от API должен быть словарем")
        raise TypeError("Ответ от API должен быть словарем")
    if not response:
        logging.error("Ответ от API пустой")
        raise ValueError("Ответ от API пустой")
    if "error" in response:
        logging.error(f'Ошибка при запросе к API: {response["error"]}')
        raise requests.exceptions.HTTPError(response["error"])
    if "homeworks" not in response or "current_date" not in response:
        logging.error("Отсутствие ожидаемых ключей в ответе API")
        raise KeyError("Отсутствие ожидаемых ключей в ответе API")
    if not isinstance(response["homeworks"], list):
        logging.error('Данные под ключом "homeworks" должны быть списком')
        raise TypeError('Данные под ключом "homeworks" должны быть списком')


def parse_status(homework):
    """Парсинг статуса работы."""
    if "homework_name" not in homework:
        logging.error('Отсутствие ключа "homework_name" в ответе API')
        raise KeyError('Отсутствие ключа "homework_name" в ответе API')
    homework_name = homework.get("homework_name")
    status = homework.get("status")
    if status not in HOMEWORK_VERDICTS:
        logging.error(f"Неожиданный статус домашней работы: {status}")
        raise ValueError(f"Неожиданный статус домашней работы: {status}")
    verdict = HOMEWORK_VERDICTS.get(homework.get("status"))
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            homework_response = get_api_answer(timestamp)
            check_response(homework_response)
            homeworks = homework_response.get("homeworks", [])
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                timestamp = homeworks[0].get("date_updated")

        except Exception as error:
            logging.error(f"Ошибка при запросе к основному API: {error}")
        time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
