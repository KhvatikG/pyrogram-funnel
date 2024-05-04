from loguru import logger

logger.add('logs/log.log', rotation='10 mb', level='DEBUG')
