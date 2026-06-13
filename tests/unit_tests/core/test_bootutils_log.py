"""Tests for the daily-grouped rotating log file handler.

Regression coverage for the bug where a long-running process names its log
file after the *start* day and keeps appending to it across midnight, so no
file ever appears for the current day. See
``langbot.pkg.core.bootutils.log.DailyGroupedRotatingFileHandler``.
"""

from __future__ import annotations

import logging
import os
import re

import langbot.pkg.core.bootutils.log as logmod
from langbot.pkg.core.bootutils.log import DailyGroupedRotatingFileHandler

# Mirror of the cleanup pattern in api/http/service/maintenance.py.
MAINTENANCE_LOG_FILE_PATTERN = re.compile(r'^langbot-(\d{4}-\d{2}-\d{2})\.log(?:\.\d+)?$')


def _listing(directory):
    return sorted(os.listdir(directory))


def _make_logger(handler, name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class TestDailyGroupedRotatingFileHandler:
    def _patch_date(self, monkeypatch, box):
        """Make the handler read its current date from ``box['date']``."""

        def fake_strftime(fmt, t=None):
            if fmt == '%Y-%m-%d':
                return box['date']
            return '00:00:00'

        monkeypatch.setattr(logmod.time, 'strftime', fake_strftime)

    def test_initial_file_named_for_current_day(self, tmp_path, monkeypatch):
        box = {'date': '2026-06-08'}
        self._patch_date(monkeypatch, box)

        handler = DailyGroupedRotatingFileHandler(str(tmp_path), max_bytes=10_000, backup_count=3)
        logger = _make_logger(handler, 'lb_logtest_initial')
        logger.info('hello')
        handler.close()

        assert _listing(tmp_path) == ['langbot-2026-06-08.log']

    def test_same_day_size_rotation_creates_numbered_backups(self, tmp_path, monkeypatch):
        box = {'date': '2026-06-08'}
        self._patch_date(monkeypatch, box)

        handler = DailyGroupedRotatingFileHandler(str(tmp_path), max_bytes=200, backup_count=3)
        logger = _make_logger(handler, 'lb_logtest_size')
        for i in range(40):
            logger.info('padding line to exceed maxBytes %d', i)
        handler.close()

        files = _listing(tmp_path)
        assert 'langbot-2026-06-08.log' in files
        assert any(f.startswith('langbot-2026-06-08.log.') for f in files)

    def test_rolls_to_new_file_when_day_changes(self, tmp_path, monkeypatch):
        box = {'date': '2026-06-08'}
        self._patch_date(monkeypatch, box)

        handler = DailyGroupedRotatingFileHandler(str(tmp_path), max_bytes=10_000, backup_count=3)
        logger = _make_logger(handler, 'lb_logtest_midnight')
        logger.info('day1 line')

        # Simulate crossing midnight within the same running process.
        box['date'] = '2026-06-09'
        logger.info('day2 line after midnight')
        handler.close()

        files = _listing(tmp_path)
        assert 'langbot-2026-06-08.log' in files
        assert 'langbot-2026-06-09.log' in files

        day2 = (tmp_path / 'langbot-2026-06-09.log').read_text(encoding='utf-8')
        assert 'day2 line after midnight' in day2
        assert 'day1 line' not in day2

    def test_rollover_repeats_across_multiple_days(self, tmp_path, monkeypatch):
        box = {'date': '2026-06-08'}
        self._patch_date(monkeypatch, box)

        handler = DailyGroupedRotatingFileHandler(str(tmp_path), max_bytes=10_000, backup_count=3)
        logger = _make_logger(handler, 'lb_logtest_multiday')
        for day in ('2026-06-08', '2026-06-09', '2026-06-10'):
            box['date'] = day
            logger.info('line for %s', day)
        handler.close()

        files = _listing(tmp_path)
        for day in ('2026-06-08', '2026-06-09', '2026-06-10'):
            assert f'langbot-{day}.log' in files

    def test_all_filenames_match_maintenance_cleanup_pattern(self, tmp_path, monkeypatch):
        box = {'date': '2026-06-08'}
        self._patch_date(monkeypatch, box)

        handler = DailyGroupedRotatingFileHandler(str(tmp_path), max_bytes=200, backup_count=3)
        logger = _make_logger(handler, 'lb_logtest_pattern')
        for i in range(40):
            logger.info('padding line %d', i)
        box['date'] = '2026-06-09'
        logger.info('next day line')
        handler.close()

        for name in _listing(tmp_path):
            assert MAINTENANCE_LOG_FILE_PATTERN.match(name), name
