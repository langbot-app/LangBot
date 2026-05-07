"""Tests for the safe expression evaluator that replaced eval()."""

import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from langbot.pkg.workflow.executor import _safe_eval


class TestSafeEvalLiterals:
    """Test literal value evaluation."""

    def test_integer(self):
        assert _safe_eval("42") == 42

    def test_negative_integer(self):
        assert _safe_eval("-5") == -5

    def test_float(self):
        assert _safe_eval("3.14") == pytest.approx(3.14)

    def test_string(self):
        assert _safe_eval('"hello"') == "hello"

    def test_single_quoted_string(self):
        assert _safe_eval("'world'") == "world"

    def test_true(self):
        assert _safe_eval("True") is True

    def test_false(self):
        assert _safe_eval("False") is False

    def test_none(self):
        assert _safe_eval("None") is None


class TestSafeEvalComparisons:
    """Test comparison operators."""

    def test_eq_true(self):
        assert _safe_eval("1 == 1") is True

    def test_eq_false(self):
        assert _safe_eval("1 == 2") is False

    def test_neq(self):
        assert _safe_eval("1 != 2") is True

    def test_gt(self):
        assert _safe_eval("3 > 2") is True

    def test_gte(self):
        assert _safe_eval("3 >= 3") is True

    def test_lt(self):
        assert _safe_eval("1 < 2") is True

    def test_lte(self):
        assert _safe_eval("2 <= 2") is True

    def test_string_eq(self):
        assert _safe_eval('"hello" == "hello"') is True

    def test_string_neq(self):
        assert _safe_eval('"a" != "b"') is True

    def test_chained_comparison(self):
        assert _safe_eval("1 < 2 < 3") is True

    def test_chained_comparison_false(self):
        assert _safe_eval("1 < 2 > 3") is False

    def test_is_none(self):
        assert _safe_eval("None is None") is True

    def test_is_not_none(self):
        assert _safe_eval("1 is not None") is True


class TestSafeEvalIn:
    """Test 'in' / 'not in' operators."""

    def test_in_list(self):
        assert _safe_eval('"abc" in ["abc", "def"]') is True

    def test_not_in_list(self):
        assert _safe_eval('"x" not in ["a", "b"]') is True

    def test_int_in_list(self):
        assert _safe_eval("2 in [1, 2, 3]") is True

    def test_in_string(self):
        assert _safe_eval('"lo" in "hello"') is True


class TestSafeEvalBooleanLogic:
    """Test and / or / not operators."""

    def test_and_true(self):
        assert _safe_eval("True and True") is True

    def test_and_false(self):
        assert _safe_eval("True and False") is False

    def test_or_true(self):
        assert _safe_eval("False or True") is True

    def test_or_false(self):
        assert _safe_eval("False or False") is False

    def test_not_true(self):
        assert _safe_eval("not False") is True

    def test_not_false(self):
        assert _safe_eval("not True") is False

    def test_complex_boolean(self):
        assert _safe_eval("(1 == 1) and (2 > 1) or False") is True


class TestSafeEvalArithmetic:
    """Test arithmetic operators."""

    def test_add(self):
        assert _safe_eval("1 + 2") == 3

    def test_sub(self):
        assert _safe_eval("5 - 3") == 2

    def test_mul(self):
        assert _safe_eval("3 * 4") == 12

    def test_div(self):
        assert _safe_eval("10 / 3") == pytest.approx(3.333, abs=0.01)

    def test_floor_div(self):
        assert _safe_eval("10 // 3") == 3

    def test_mod(self):
        assert _safe_eval("10 % 3") == 1

    def test_combined_arithmetic_comparison(self):
        assert _safe_eval("1 + 2 == 3") is True


class TestSafeEvalSecurity:
    """Ensure dangerous constructs are rejected."""

    def test_import_blocked(self):
        with pytest.raises((ValueError, SyntaxError)):
            _safe_eval('__import__("os")')

    def test_function_call_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval('print("hello")')

    def test_open_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval('open("/etc/passwd")')

    def test_attribute_access_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval('"hello".__class__')

    def test_subscript_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval('[1,2,3][0]')

    def test_class_subclasses_blocked(self):
        with pytest.raises((ValueError, SyntaxError)):
            _safe_eval('().__class__.__subclasses__()')

    def test_exec_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval('exec("import os")')

    def test_eval_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval('eval("1+1")')

    def test_lambda_blocked(self):
        with pytest.raises((ValueError, SyntaxError)):
            _safe_eval('lambda: 1')

    def test_variable_reference_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval('x + 1')
