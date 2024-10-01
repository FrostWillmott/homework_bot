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
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params={"from_date": timestamp}
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
        error_message = "Ответ от API должен быть словарем"
        logging.error(error_message)
        raise TypeError(error_message)
    if not response:
        error_message = "Ответ от API пустой"
        logging.error(error_message)
        raise ValueError(error_message)
    if "error" in response:
        error_message = f'Ошибка при запросе к API: {response["error"]}'
        logging.error(error_message)
        raise requests.exceptions.HTTPError(response["error"])
    if "homeworks" not in response or "current_date" not in response:
        error_message = "Отсутствие ожидаемых ключей в ответе API"
        logging.error(error_message)
        raise KeyError(error_message)
    if not isinstance(response["homeworks"], list):
        error_message = 'Данные под ключом "homeworks" должны быть списком'
        logging.error(error_message)
        raise TypeError(error_message)


def parse_status(homework):
    """Парсинг статуса работы."""
    if "homework_name" not in homework:
        error_message = 'Отсутствие ключа "homework_name" в ответе API'
        logging.error(error_message)
        raise KeyError(error_message)
    homework_name = homework.get("homework_name")
    status = homework.get("status")
    if status not in HOMEWORK_VERDICTS:
        error_message = f"Неожиданный статус домашней работы: {status}"
        logging.error(error_message)
        raise ValueError(error_message)
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
            if isinstance(homework_response, (AssertionError, RuntimeError)):
                send_message(bot, str(homework_response))
            check_results = check_response(homework_response)
            if isinstance(check_results, (TypeError, ValueError, KeyError)):
                send_message(bot, str(check_results))
            homeworks = homework_response.get("homeworks", [])
            if homeworks:
                message = parse_status(homeworks[0])
                if isinstance(message, (ValueError, KeyError)):
                    send_message(bot, str(message))
                send_message(bot, message)
                timestamp = homework_response.get("current_date")

        except Exception as error:
            logging.error(f"Ошибка при запросе к основному API: {error}")
        time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
