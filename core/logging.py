import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "core/logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

def _setup_logger(name, filename):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(LOG_DIR / filename)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False  

    return logger


cleaner_logger = _setup_logger("cleaners", "cleaners.log")
llm_extractor_logger = _setup_logger("llm_extractor", "llm_extractor.log")
scraper_logger = _setup_logger("scraper", "scraper.log")
google_logger = _setup_logger("google_ingestor", "google_ingestor.log")
matcher_logger = _setup_logger("matcher", "matcher.log")
email_logger = _setup_logger("email_service", "email_service.log")
