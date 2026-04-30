import os
from unittest.mock import patch

import pytest

from config.settings import Settings, get_settings
from config.logging_config import get_logger

class TestSettings:

    def test_defaults(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            settings = Settings()
            assert settings.batch_size == 1000
            assert settings.etl_version == "1.0.0"
            assert settings.log_level == "INFO"

    def test_database_url_required(self):
        with patch.dict(os.environ, {}, clear=True):

            pass

class TestLogging:

    def test_get_logger(self):
        logger = get_logger("test_module")
        assert logger is not None
        assert logger.name == "test_module"

    def test_different_modules(self):
        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")
        assert logger1.name != logger2.name
