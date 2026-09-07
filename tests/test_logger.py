"""Debug-log level gating: warn() writes to the file, log() does not."""
import logging
import os

import logger


def test_debug_file_captures_warn_not_info(tmp_path, capsys):
    path = os.path.join(tmp_path, "notebook-debug.log")
    logger.enable_debug_log(path)
    try:
        logger.log("stage", {"progress": "info-only"})   # stdout only
        logger.warn("stage", {"msg": "a warning"})        # stdout + file
        logger.error("stage", {"msg": "an error"})        # stdout + file

        with open(path) as f:
            contents = f.read()
    finally:
        # detach the handler so other tests don't inherit it
        for h in list(logger._file_logger.handlers):
            if isinstance(h, logging.FileHandler):
                logger._file_logger.removeHandler(h)
                h.close()

    assert "info-only" not in contents
    assert "a warning" in contents
    assert "an error" in contents
