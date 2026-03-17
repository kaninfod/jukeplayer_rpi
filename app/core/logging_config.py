"""
Pi Client Logging Configuration
Sets up syslog + file + console logging (mirroring backend pattern)
"""

import logging
import logging.handlers
import socket
import os


def setup_logging(log_file=None, level=None):
    """
    Configure logging for Pi client with syslog + file fallback.
    
    Args:
        log_file: Path to log file. If None, uses config default.
        level: Logging level. If None, uses config level.
    """
    from app.config import config
    
    # Use provided values or config defaults
    if log_file is None:
        log_file = config.LOG_FILE
    if level is None:
        level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Don't add duplicate handlers if already configured
    if logger.handlers:
        return
    
    hostname = socket.gethostname()
    formatter = logging.Formatter(f'{hostname} %(name)s: %(levelname)s %(message)s')
    
    # === SYSLOG HANDLER (Primary) ===
    syslog_configured = False
    if config.LOG_SERVER_HOST and config.LOG_SERVER_HOST.lower() not in ['localhost', '127.0.0.1', '']:
        try:
            syslog_address = (config.LOG_SERVER_HOST, config.LOG_SERVER_PORT)
            syslog_handler = logging.handlers.SysLogHandler(address=syslog_address)
            syslog_handler.setFormatter(formatter)
            logging.getLogger().addHandler(syslog_handler)
            syslog_configured = True
            logging.info(f"✅ Syslog configured: {config.LOG_SERVER_HOST}:{config.LOG_SERVER_PORT}")
        except Exception as e:
            logging.warning(f"⚠️  Syslog server unavailable ({config.LOG_SERVER_HOST}:{config.LOG_SERVER_PORT}): {e}")
            logging.info("   Falling back to file logging only")
    else:
        logging.debug("Syslog not configured (LOG_SERVER_HOST empty or localhost)")
    
    # === FILE HANDLER (Fallback/Always) ===
    try:
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)
    except Exception as e:
        logging.warning(f"Could not create log file: {e}")
    
    # === CONSOLE HANDLER (Always) ===
    screen_handler = logging.StreamHandler()
    screen_handler.setFormatter(formatter)
    logging.getLogger().addHandler(screen_handler)
    
    # === SUPPRESS NOISY THIRD-PARTY LOGS ===
    for lib in ["httpx", "asyncio", "urllib3"]:
        logging.getLogger(lib).setLevel(logging.WARNING)
