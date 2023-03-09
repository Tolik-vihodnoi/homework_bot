import logging
import os
import sys
import time
from http import HTTPStatus
from typing import NoReturn, Optional, Union

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APIError, NotForSending, TokenError


load_dotenv()

PRACTICUM_TOKEN: Optional[str] = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: Optional[str] = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: Optional[str] = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD: int = 5
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: dict[str, str] = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS: dict[str, str] = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> NoReturn:
    """Check if tokens are None."""
    token_names: tuple[str, str, str] = (
        'PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'
    )
    missing_tokens: list[Optional[str]] = [
        i for i in token_names if globals().get(i) is None
    ]
    if not missing_tokens:
        logging.debug(
            f"The vars: pract={PRACTICUM_TOKEN}, "
            f"tele={TELEGRAM_TOKEN}, tele_chat={TELEGRAM_CHAT_ID}"
        )
        try:
            int(TELEGRAM_CHAT_ID)
        except ValueError:
            raise TokenError('Variable TELEGRAM_CHAT_ID is not a number')
    else:
        logging.critical(f'This tokens have None value: {missing_tokens}')
        raise TokenError('Environment has no needed tokens!')


def send_message(bot: telegram.bot.Bot, message: str) -> NoReturn:
    """Send the message to TELEGRAM_CHAT_ID by passed bot instance."""
    logging.debug(f'Trying to send the message to {TELEGRAM_CHAT_ID}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, str(message))
    except telegram.error.TelegramError:
        logging.error('The message hasn\'t been sent!')
        raise NotForSending('The message hasn\'t been sent')
    logging.debug('The message has been sent!')


def get_api_answer(timestamp: int) -> dict[str, Union[list, int]]:
    """Get int timestamp and return API response in dict type."""
    logging.debug(f'Trying to get API answer with ts={timestamp}')
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.RequestException as e:
        raise APIError(
            f'Crushed while request to url={ENDPOINT} '
            f'with params from_date={timestamp}. {e}'
        )
    if response.status_code != HTTPStatus.OK:
        raise APIError(
            f'The status of response is {response.status_code}. '
            f'Url={ENDPOINT}. Params: from_date={timestamp}'
        )
    logging.debug('Success request to ENDPOINT')
    return response.json()


def check_response(response: dict[str, Union[list, int]]) -> NoReturn:
    """Look for the key 'homeworks' in the keys of response.

    Check if the key is exists and has the right type of its value.
    """
    logging.debug(f'Trying to check response. Response: {response}')
    if not isinstance(response, dict):
        raise TypeError("Unexpected type of the response")
    if 'homeworks' not in response.keys():
        raise KeyError('The response has no key "homeworks"!')
    if not isinstance(response['homeworks'], list):
        raise TypeError("Unexpected type of the variable 'homeworks'")
    logging.debug(f'The check has been passed successfully')


def parse_status(homework: dict[str, Union[int, str]]) -> str:
    """
    Get dict, parse with the key 'homework_name'.

    Check for value of status in dict HOMEWORK_VERDICTS.
    """
    logging.debug('Trying to parse the status of homework')
    if not isinstance(homework, dict):
        raise TypeError('Homework is not a dict instance')
    if 'homework_name' not in homework.keys():
        raise KeyError('Dict "homework" has no key "homework_name"')
    homework_name: str = homework['homework_name']
    status: Optional[str] = homework.get('status')
    if status not in HOMEWORK_VERDICTS.keys():
        raise ValueError(
            f'The received status "{status}" is not '
            f'found in the verdict dictionary'
        )
    verdict: str = HOMEWORK_VERDICTS[status]
    logging.debug('Parsed success')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> NoReturn:
    """Do main logical job of the bot."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp: int = int(time.time())
    prev_msg: str = ''

    while True:
        try:
            logging.debug(
                f'New loop: timestamp={timestamp}, '
                f'evaluating_cur_time={int(time.time())}'
            )
            r_json = get_api_answer(timestamp)
            check_response(r_json)
            works = r_json['homeworks']
            if works:
                cur_msg: str = parse_status(works[0])
                if prev_msg != cur_msg:
                    send_message(bot, cur_msg)
                    prev_msg = cur_msg
                timestamp = r_json.get('current_date', int(time.time()) - 1)
            else:
                logging.debug('Have no updated satus')
        except NotForSending:
            logging.error(
                f'The var "timestamp" won\'t be updated this loop. Will try '
                f'to send the message again in {RETRY_PERIOD} seconds'
            )
        except Exception as error:
            cur_msg = f'Сбой в работе программы: {error}'
            logging.error(cur_msg)
            if prev_msg != cur_msg:
                try:
                    send_message(bot, cur_msg)
                    prev_msg = cur_msg
                except NotForSending:
                    pass
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        handlers=(logging.StreamHandler(sys.stdout), ),
        format=(
            '%(asctime)s [%(levelname)s]:%(funcName)s:%(lineno)s - %(message)s'
        ),
        level=logging.DEBUG
    )
    main()
