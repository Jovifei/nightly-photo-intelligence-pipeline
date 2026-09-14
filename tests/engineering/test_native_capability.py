"""Classification tests are not evidence of creating a native Windows symlink."""

from __future__ import annotations

import unittest

from nightly_photo_intelligence_pipeline.engineering.native_capability import symlink_privilege_gap


def observed_error(code):
    error = OSError(13, "redacted fixture path must not be echoed")
    error.winerror = code
    return error


class NativeCapabilityTests(unittest.TestCase):
    def test_windows_privilege_not_held_is_precise_gap(self):
        self.assertEqual(
            symlink_privilege_gap(observed_error(1314), platform="win32"),
            "native symlink privilege unavailable: platform=win32 winerror=1314 errno=13",
        )

    def test_windows_other_errors_are_not_skips(self):
        for code in (2, 3, 5, 32, 87, 183, 4390):
            with self.subTest(winerror=code):
                self.assertIsNone(symlink_privilege_gap(observed_error(code), platform="win32"))

    def test_unknown_oserror_does_not_prove_privilege_gap(self):
        self.assertIsNone(symlink_privilege_gap(OSError("fixture"), platform="win32"))

    def test_wrong_platform_does_not_receive_windows_skip(self):
        for platform in ("linux", "darwin", "cygwin", "unknown"):
            with self.subTest(platform=platform):
                self.assertIsNone(symlink_privilege_gap(observed_error(1314), platform=platform))

    def test_error_code_type_is_not_coerced(self):
        for code in ("1314", 1314.0, True, None):
            with self.subTest(code=repr(code)):
                self.assertIsNone(symlink_privilege_gap(observed_error(code), platform="win32"))

    def test_diagnostic_never_echoes_exception_text(self):
        result = symlink_privilege_gap(observed_error(1314), platform="win32")
        self.assertNotIn("fixture path", result)


if __name__ == "__main__":
    unittest.main()
