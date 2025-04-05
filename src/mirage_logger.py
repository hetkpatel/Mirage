import os
import logging
from logging.handlers import RotatingFileHandler


class HostingLoggerSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HostingLoggerSingleton, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance

    def _initialize_logger(self):
        self.logger = logging.getLogger("Mirage Hosting")
        self.logger.setLevel(logging.DEBUG)

        handler = RotatingFileHandler(
            os.path.join("/mirage/logs", "hosting.log"),
            maxBytes=10**6,
            backupCount=5,
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(name)s %(levelname)s :: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handler.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

    def get_logger(self):
        return self.logger


class ProcessingLoggerSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProcessingLoggerSingleton, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance

    def _initialize_logger(self):
        self.logger = logging.getLogger("Mirage Processing")
        self.logger.setLevel(logging.DEBUG)

        handler = RotatingFileHandler(
            os.path.join("/mirage/logs", "processing.log"),
            maxBytes=10**6,
            backupCount=5,
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(name)s %(levelname)s :: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handler.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

    def get_logger(self):
        return self.logger
