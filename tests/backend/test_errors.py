import unittest

from errors import AppError, error_payload, truncate_detail


class ErrorHelperTests(unittest.TestCase):
    def test_error_payload_omits_empty_detail(self):
        payload = error_payload("youtube_timeout", "YouTube search timed out.")

        self.assertEqual(payload, {
            "code": "youtube_timeout",
            "message": "YouTube search timed out.",
        })

    def test_error_payload_includes_truncated_detail(self):
        payload = error_payload("download_failed", "Download failed.", "x" * 510)

        self.assertEqual(payload["code"], "download_failed")
        self.assertEqual(payload["message"], "Download failed.")
        self.assertEqual(len(payload["detail"]), 500)
        self.assertTrue(payload["detail"].endswith("..."))

    def test_app_error_exposes_payload(self):
        error = AppError(
            code="processing_failed",
            message="Processing failed.",
            detail="Demucs failed",
        )

        self.assertEqual(str(error), "Processing failed.")
        self.assertEqual(error.as_dict(), {
            "code": "processing_failed",
            "message": "Processing failed.",
            "detail": "Demucs failed",
        })

    def test_truncate_detail_handles_none(self):
        self.assertIsNone(truncate_detail(None))


if __name__ == "__main__":
    unittest.main()
