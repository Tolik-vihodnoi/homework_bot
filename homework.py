import logging
import os
import time
from http import HTTPStatus
from typing import NoReturn, Optional

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APIError, TokenError

logging.basicConfig(
    handlers=(logging.StreamHandler(), ),
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO
)

load_dotenv()

PRACTICUM_TOKEN: Optional[str] = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: Optional[str] = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: Optional[str] = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD: int = 600
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: dict = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS: dict = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> NoReturn:
    """Check if tokens are None."""
    envs: tuple[Optional[str], Optional[str], Optional[str]]
    envs = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    if None not in envs:
        logging.debug(
            f"The vars: pract={PRACTICUM_TOKEN}, "
            f"tele={TELEGRAM_TOKEN}, tele_chat={TELEGRAM_CHAT_ID}"
        )
        try:
            int(TELEGRAM_CHAT_ID)
        except ValueError:
            raise TokenError('Variable TELEGRAM_CHAT_ID is not a number')
    else:
        logging.critical('One or more tokens are None')
        raise TokenError('Environment has no needed tokens!')


def send_message(bot: telegram.bot.Bot, message: str) -> NoReturn:
    """Send the message to TELEGRAM_CHAT_ID by passed bot instance."""
    try:
        msg = bot.send_message(TELEGRAM_CHAT_ID, str(message))
        logging.debug(f'Type: {type(msg)}. Msg: {msg}')
        if isinstance(msg, telegram.message.Message):
            logging.debug('The message has been sent!')
        else:
            logging.error(f'Message hasn\'t been delivered. The msg = {msg},'
                          f'and its type = {type(msg)}')
    except telegram.error.BadRequest:
        logging.error(f'Chat id {TELEGRAM_CHAT_ID} not found!')
    except AttributeError:
        logging.error('Seems like it is not a bot instance!')
    except Exception as e:
        logging.error(f'Unexpected error: {e}')


def get_api_answer(timestamp: int) -> dict:
    """Get int timestamp and return API response in dict type."""
    if not isinstance(timestamp, int):
        raise TypeError
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.RequestException as e:
        raise APIError(f'Crushed with RequestException error: {e}')
    except Exception as e:
        raise APIError(f'Crushed with unexpected error: {e}')
    if response.status_code == HTTPStatus.OK:
        r_json = response.json()
    else:
        raise APIError(
            f'The status of response is {response.status_code}'
        )
    logging.debug('Success request to ENDPOINT')
    return r_json


def check_response(response: dict) -> tuple[int, list]:
    """Check if keys 'current_date' and 'homeworks' exist and have the
    right types.
    """
    try:
        cur_date: int = response['current_date']
        works: list = response['homeworks']
        if isinstance(cur_date, int) and isinstance(works, list):
            return cur_date, works
        else:
            raise TypeError(
                "Unexpected types of variables 'cur_date' and 'works'"
            )
    except TypeError:
        raise TypeError("The passed response is not a dict type!")
    except Exception as e:
        raise APIError(f'Unexpected error: {e}')


def parse_status(homework: dict) -> str:
    """Get dict, parse with the keys 'status', 'homework_name',
    check for value of status in dict HOMEWORK_VERDICTS.
    """
    if not isinstance(homework, dict):
        raise TypeError('Homework is not a dict instance')
    try:
        status: int = homework['status']
        homework_name: str = homework['homework_name']
        verdict: str = HOMEWORK_VERDICTS[status]
    except KeyError:
        raise APIError('Arg homework has no key like this')
    except TypeError:
        raise APIError('Passed key is not correct!')
    except Exception as e:
        raise APIError(f'Unexpected error: {e}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> NoReturn:
    """Main logical job of the bot."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp: int = int(time.time())

    while True:
        try:
            r_json = get_api_answer(timestamp)
            cur_date, works = check_response(r_json)
            logging.debug(
                f'New loop, vars: ts={timestamp}, cur_date={cur_date}'
            )
            timestamp = cur_date + RETRY_PERIOD
            if len(works) > 0:
                send_message(bot, parse_status(works[0]))
            else:
                logging.debug('Have no updated satus')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
