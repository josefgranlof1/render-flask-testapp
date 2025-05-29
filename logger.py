import logging
import sys

def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)  # ensure logger will handle INFO+ messages :contentReference[oaicite:3]{index=3}

    # Prevent duplicate handlers if this is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()    # remove existing handlers :contentReference[oaicite:4]{index=4}

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)  # ensure handler will handle INFO+ messages :contentReference[oaicite:5]{index=5}

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s - %(lineno)s - %(name)s - %(message)s'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)       # **must** add handler to logger :contentReference[oaicite:6]{index=6}
    logger.propagate = False         # optional: prevent messages bubbling up to root :contentReference[oaicite:7]{index=7}

    return logger
