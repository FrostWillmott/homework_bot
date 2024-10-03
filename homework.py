import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot, apihelper

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


def check_tokens():
    """Проверка наличия токенов."""
    source = ("PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")
    for token in source:
        if not globals().get(token):
            logging.critical(
                f"Отсутствие обязательных переменных окружения"
                f" во время запуска бота: {token}"
            )
            raise ValueError(f"Не указан токен {token}")


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    logging.debug(f"Отправка сообщения в Telegram: {message}")
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f"Сообщение отправлено в Telegram: {message}")
    except (apihelper.ApiException, requests.RequestException) as error:
        raise RuntimeError(
            f"Ошибка при отправке сообщения в Telegram: {error}"
        )


def get_api_answer(timestamp):
    """Получение данных от API."""
    logging.debug(f"Запрос к API с параметром from_date: {timestamp}")
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params={"from_date": timestamp}
        )
    except requests.RequestException as error:
        logging.error(f"Ошибка при запросе к API: {error}")
        raise ConnectionError(
            f"Ошибка при запросе к API: {error}"
            f"Эндпоинт: {ENDPOINT},"
            f" Параметры: {{'from_date': {timestamp}}}"
        )
    if homework_statuses.status_code != HTTPStatus.OK:
        raise ConnectionError(
            f"Эндпоинт {ENDPOINT} недоступен."
            f"Код ответа: {homework_statuses.status_code}"
            f"Причина: {homework_statuses.reason}"
        )
    logging.debug(f"Ответ от API: {homework_statuses.json()}")
    return homework_statuses.json()


def check_response(response):
    """Проверка ответа от API."""
    logging.debug(f"Проверка ответа от API: {response}")
    if not isinstance(response, dict):
        error_message = (
            f"Ответ от API должен быть словарем, получен тип: {type(response)}"
        )
        raise TypeError(error_message)
    if "homeworks" not in response:
        error_message = "Отсутствие ожидаемых ключей в ответе API"
        raise KeyError(error_message)
    if not isinstance(response["homeworks"], list):
        error_message = (
            f'Данные под ключом "homeworks" должны быть списком,'
            f" получен тип: {type(response)}"
        )
        raise TypeError(error_message)
    logging.debug("Проверка ответа от API пройдена успешно")


def parse_status(homework):
    """Парсинг статуса работы."""
    logging.debug(f"Парсинг статуса работы: {homework}")
    if "homework_name" not in homework:
        error_message = 'Отсутствие ключа "homework_name" в ответе API'
        raise KeyError(error_message)
    homework_name = homework.get("homework_name")
    if "status" not in homework:
        error_message = 'Отсутствие ключа "status" в ответе API'
        raise KeyError(error_message)
    status = homework.get("status")
    if status not in HOMEWORK_VERDICTS:
        error_message = f"Неожиданный статус домашней работы: {status}"
        raise ValueError(error_message)
    verdict = HOMEWORK_VERDICTS.get(homework.get("status"))
    logging.debug(f"Парсинг статуса работы завершен: {verdict}")
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = None

    while True:
        try:
            homework_response = get_api_answer(timestamp)
            check_response(homework_response)
            homeworks = homework_response.get("homeworks", [])
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logging.debug("Новых статусов нет")
            timestamp = homework_response.get("current_date", int(time.time()))

        except Exception as error:
            error_message = f"Возникла ошибка: {error}"
            logging.error(error_message)
            if error_message != last_error_message:
                try:
                    send_message(bot, error_message)
                    last_error_message = error_message
                except RuntimeError as error:
                    logging.error(
                        f"Ошибка при отправке сообщения в Telegram: {error}",
                        exc_info=True,
                    )
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s, %(levelname)s, %(message)s,"
        " %(name)s, %(funcName)s, %(lineno)d",
    )
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler(stream=sys.stdout)
    logger.addHandler(handler)
    main()
