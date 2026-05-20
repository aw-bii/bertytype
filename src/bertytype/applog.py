import sys
from pathlib import Path
from loguru import logger

LOG_PATH = Path.home() / ".bertytype" / "logs"
LOG_FILE = "bertytype.log"

logger.remove()
if sys.stderr is not None:
    logger.add(
        sys.stderr,
        format="<level>{level}</level> <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )


def init_file_logging() -> None:
    LOG_PATH.mkdir(parents=True, exist_ok=True)
    logger.add(
        LOG_PATH / LOG_FILE,
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
    )
