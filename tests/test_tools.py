"""Tests for read-only SQL validation."""

import pytest

from dq_platform.tools.agent_tools import validate_read_only_sql


def test_allows_select():
    validate_read_only_sql("SELECT 1")


def test_blocks_insert():
    with pytest.raises(ValueError):
        validate_read_only_sql("INSERT INTO t VALUES (1)")
