import json
import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exception import ApiError, IsNot200Error, JSONDecoderError

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


def check_tokens():
    """Функция проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат."""
    try:
        message_info = f'Сообщение готово к отправке: {message}'
        logging.info(message_info)
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError:
        message_error = f'Сообщение не удалось отправить: {message}'
        logging.error(message_error)
    else:
        message_info = f'Сообщение отправлено: {message}'
        logging.debug(message_info)


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
        if homework.status_code != HTTPStatus.OK:
            message_error = (f'API {ENDPOINT} недоступен, '
                             f'код ошибки {homework.status_code}')
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
    except KeyError as error:
        message = f'{error}: В ответе отсутствуют необходимые ключи'
        raise KeyError(message)
    if response['homeworks'] == []:
        return {}
    if type(response) != dict:
        response_type = type(response)
        message = f'Ответ пришел в некорректном формате: {response_type}'
        raise TypeError(message)
    homework = response.get('homeworks')
    if type(homework) != list:
        message = 'Некорректное значение в ответе у домашней работы'
        raise TypeError(message)
    return homework


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
        logging.critical('Отсутствует обязательная переменная окружения')
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
                message = 'Статус работы не изменился'
                send_message(bot, message)
                logging.debug('Нет нового статуса')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_error:
                last_error = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s, %(message)s, %(lineno)d, %(name)s',
        filemode='w',
        filename='program.log',
        level=logging.INFO,
    )
    main()
