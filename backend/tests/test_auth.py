import os
import unittest

from fastapi import HTTPException

os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("READ_API_KEY", "test-read-key")

from app.auth import require_ingest_key, require_read_key
from app.config import settings


class AuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_ingest = settings.ingest_api_key
        self.original_read = settings.read_api_key
        settings.ingest_api_key = "test-ingest-key"
        settings.read_api_key = "test-read-key"

    def tearDown(self) -> None:
        settings.ingest_api_key = self.original_ingest
        settings.read_api_key = self.original_read

    def test_ingest_key_accepts_exact_match(self) -> None:
        require_ingest_key("test-ingest-key")

    def test_ingest_key_rejects_missing_or_invalid_value(self) -> None:
        for value in (None, "wrong"):
            with self.subTest(value=value), self.assertRaises(HTTPException) as raised:
                require_ingest_key(value)
            self.assertEqual(401, raised.exception.status_code)

    def test_read_key_is_independent_from_ingest_key(self) -> None:
        require_read_key("test-read-key")
        with self.assertRaises(HTTPException) as raised:
            require_read_key("test-ingest-key")
        self.assertEqual(401, raised.exception.status_code)

    def test_runtime_validation_rejects_placeholder(self) -> None:
        settings.read_api_key = "changeme"
        with self.assertRaises(RuntimeError):
            settings.validate_runtime_secrets()


if __name__ == "__main__":
    unittest.main()
