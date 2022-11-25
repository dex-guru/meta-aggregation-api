from contextvars import ContextVar
from logging import LoggerAdapter, getLogger
from logging.config import dictConfig
from typing import Optional
from uuid import uuid4

from config import config

CORRELATION_ID = "cid"
SESSION_ID = "sid"
CHAIN_ID = "chain_id"
PIPELINE = "pipeline"
ERR = "err"  # error object log argument
ERR_TYPE = "err_type"  # error type log argument

# This field is keyword argument from <https://github.com/python/cpython/blob/3.10/Lib/logging/__init__.py#L1600>
#   and never changed.
EXTRA = "extra"

CONFIG = dict(
    # See: <https://docs.python.org/3.7/library/logging.config.html#logging.config.fileConfig>
    # and find `disable_existing_loggers`, it's same configuration parameter as for dictConfig function.
    disable_existing_loggers=False,
    version=1,
    formatters={
        'simple': {
            'format': '%(asctime)s - %(filename)s:%(lineno)s:%(funcName)s - %(levelname)s - %(message)s'
        },
        'logstash': {
            '()': 'logstash_formatter.LogstashFormatterV1'
        }
    },
    handlers={
        'console': {
            'class': 'logging.StreamHandler',
            'level': config.LOGGING_LEVEL,
            'formatter': 'simple',
            'stream': 'ext://sys.stdout'
        },
        'logstash': {
            'level': config.LOGSTASH_LOGGING_LEVEL,
            'class': 'logstash_async.handler.AsynchronousLogstashHandler',
            'transport': 'logstash_async.transport.TcpTransport',
            'formatter': 'logstash',
            'host': config.LOGSTASH,
            'port': config.PORT,
            'database_path': None,
            'event_ttl': 30  # sec
        }
    },
    root={
        'handlers': config.LOG_HANDLERS,
        'level': config.LOGGING_LEVEL,
    },
)

correlation_id = ContextVar(CORRELATION_ID, default=uuid4().hex)
session_id = ContextVar(SESSION_ID, default=None)


class CustomContextLogger(LoggerAdapter):

    def __init__(self, logger, extra):
        super(CustomContextLogger, self).__init__(logger, extra)

    def process(self, msg, kwargs):
        if EXTRA not in kwargs:
            kwargs[EXTRA] = self.extra
        else:
            kwargs[EXTRA].update(self.extra)

        # assigning a request correlation key to all log messages
        kwargs[EXTRA][CORRELATION_ID] = self.get_correlation_id()

        sid = kwargs[EXTRA].get(SESSION_ID, self.get_session_id())
        if sid:
            # assigning a user session correlation key to all log messages
            kwargs[EXTRA][SESSION_ID] = sid

        if ERR in kwargs[EXTRA] and ERR_TYPE not in kwargs[EXTRA]:
            kwargs[EXTRA][ERR_TYPE] = type(kwargs[EXTRA][ERR]).__name__

        return msg, kwargs

    @staticmethod
    def get_correlation_id():
        return correlation_id.get()

    @staticmethod
    def get_session_id():
        return session_id.get()


def get_logger(name: str, extra: Optional[dict] = None, corr_id: Optional[str] = None) -> "CustomContextLogger":
    dictConfig(CONFIG)

    extra = extra or {}
    if config.CHAIN_ID and CHAIN_ID not in extra:
        extra[CHAIN_ID] = config.CHAIN_ID
    if config.PIPELINE and PIPELINE not in extra:
        extra[PIPELINE] = config.PIPELINE

    if corr_id:
        correlation_id.set(corr_id)

    logger = CustomContextLogger(getLogger(name), extra)
    return logger


def set_correlation_id(corr_id: str):
    correlation_id.set(corr_id)


def set_new_correlation_id():
    set_correlation_id(uuid4().hex)


def set_session_id(sid: str):
    session_id.set(sid)