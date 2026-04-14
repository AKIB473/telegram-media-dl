"""Tests for telegram_media_dl.utils."""
import pytest

from telegram_media_dl.utils import (
    format_duration,
    format_size,
    is_valid_url,
    make_progress_bar,
)


class TestIsValidUrl:
    def test_youtube_watch(self):
        assert is_valid_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_youtube_short(self):
        assert is_valid_url("https://youtu.be/dQw4w9WgXcQ")

    def test_instagram(self):
        assert is_valid_url("https://www.instagram.com/p/ABC123/")

    def test_tiktok(self):
        assert is_valid_url("https://www.tiktok.com/@user/video/1234567890")

    def test_twitter(self):
        assert is_valid_url("https://twitter.com/user/status/123")

    def test_x_com(self):
        assert is_valid_url("https://x.com/user/status/123")

    def test_unsupported_site(self):
        assert not is_valid_url("https://example.com/video.mp4")

    def test_plain_text(self):
        assert not is_valid_url("not a url at all")

    def test_ftp_scheme(self):
        assert not is_valid_url("ftp://youtube.com/watch?v=abc")

    def test_empty_string(self):
        assert not is_valid_url("")


class TestFormatSize:
    def test_bytes(self):
        assert format_size(512) == "512.0 B"

    def test_kilobytes(self):
        assert format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self):
        assert format_size(2 * 1024 ** 3) == "2.0 GB"


class TestFormatDuration:
    def test_none(self):
        assert format_duration(None) == "Unknown"

    def test_zero(self):
        assert format_duration(0) == "Unknown"

    def test_seconds_only(self):
        assert format_duration(45) == "00:45"

    def test_minutes_and_seconds(self):
        assert format_duration(125) == "02:05"

    def test_hours(self):
        assert format_duration(3661) == "01:01:01"


class TestMakeProgressBar:
    def test_zero_percent(self):
        bar = make_progress_bar(0, width=10)
        assert bar == "[░░░░░░░░░░] 0%"

    def test_hundred_percent(self):
        bar = make_progress_bar(100, width=10)
        assert bar == "[██████████] 100%"

    def test_fifty_percent(self):
        bar = make_progress_bar(50, width=10)
        assert bar == "[█████░░░░░] 50%"

    def test_custom_width(self):
        bar = make_progress_bar(25, width=4)
        assert bar == "[█░░░] 25%"

    def test_format_contains_brackets(self):
        bar = make_progress_bar(75)
        assert bar.startswith("[") and "]" in bar
