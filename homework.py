import json
import time
from dotenv import load_dotenv
import os
import telegram
import requests
import logging
from http import HTTPStatus
from exception import (IsNot200Error,
                       ApiError,
                       JSONDecoderError)


load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s'
)
handler = logging.StreamHandler()


def check_tokens():
    """Функция проверяет доступность переменных окружения."""
    is_check_tokens = all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])
    if not is_check_tokens:
        message_error = 'Отсутствует обязательная переменная окружения'
        logger.critical(message_error)
        return False
    return True


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат."""
    try:
        message_info = f'Сообщение готово к отправке: {message}'
        logger.info(message_info)
        bot.send_message(TELEGRAM_CHAT_ID, message)
        message_info = f'Сообщение отправлено: {message}'
        logger.debug(message_info)
    except telegram.TelegramError:
        message_error = f'Сообщение не удалось отправить: {message}'
        logger.error(message_error)


def get_api_answer(current_timestamp):
    """Функция делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
        status_code = homework.status_code
        if status_code != HTTPStatus.OK:
            message_error = (f'API {ENDPOINT} недоступен, '
                             f'код ошибки {status_code}')
            raise IsNot200Error(message_error)
        return homework.json()
    except requests.exceptions.RequestException as error_request:
        message_error = f'Ошибка в запросе API: {error_request}'
        raise ApiError(message_error)
    except json.JSONDecodeError as json_error:
        message_error = f'Ошибка json: {json_error}'
        raise JSONDecoderError(message_error) from json_error


def check_response(response):
    """Функция проверяет ответ API на соответствие документации."""
    try:
        response['homeworks']
    except KeyError:
        message = 'В ответе отсутствуют необходимые ключи'
        logger.error(message)
        raise KeyError(message)
    if not response['homeworks']:
        return []
    if isinstance(response['homeworks'], list):
        return response['homeworks']
    raise TypeError('Некорректное значение в ответе у домашней работы')


def parse_status(homework):
    """Функция извлекает статус домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is not None and homework_status is not None:
        if homework_status in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS.get(homework_status)
            return ('Изменился статус проверки '
                    f'работы "{homework_name}". {verdict}')
        message_error = f'Пустой статус: {homework_status}'
        raise SystemError(message_error)
    message_error = f'Пустое имя работы: {homework_name}'
    raise KeyError(message_error)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Бот включен')
    current_timestamp = int(time.time())
    last_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            response = check_response(response)
            if len(response) > 0:
                homework_status = parse_status(response[0])
                if homework_status is not None:
                    send_message(bot, homework_status)
            else:
                logger.debug('Нет нового статуса')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error:
                last_error = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
