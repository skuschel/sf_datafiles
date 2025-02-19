import ast
import io
import os
import sys
import tempfile
import unittest
import warnings
import numpy as np
import pandas as pd


from pandas.core.common import SettingWithCopyError
pd.options.mode.chained_assignment = "raise" # make SettingWithCopyWarning an exception


identity = lambda iterable: iterable


def make_temp_filename(*args, **kwargs):
    fd, fname = tempfile.mkstemp(*args, **kwargs)
    os.close(fd)
    return fname


def read_names(fname):
    with open(fname, "r") as f:
        rb = f.read()
    rb = rb.split("\n")
    rb = [i for i in rb if i != ""]
    rb = set(rb)
    return rb


def eval_str(x):
    if isinstance(x, str):
        return ast.literal_eval(x)
    return x


def load_df_from_csv(fname):
    return pd.read_csv(fname, index_col=0, dtype=object).applymap(eval_str)



class TestCase(unittest.TestCase):

#    def assertAllTrue(self, test):
#        return self.assertTrue(all(test))

#    def assertNumpyAllTrue(self, test):
#        return self.assertTrue(np.all(test))

    def assertAllEqual(self, left, right):
        return np.testing.assert_array_equal(left, right)

    def assertNotRaises(self, *exc):
        if not exc:
            exc = (Exception,)
        return _AssertNotRaisesContext(self, *exc)

    def assertStderr(self, expected_output):
        return _AssertStderrContext(self, expected_output)

    def assertStdout(self, expected_output):
        return _AssertStdoutContext(self, expected_output)

    def assertPrintsError(self, *expected_output):
        expected_output = "\n".join(expected_output) + "\n"
        return _AssertStderrContext(self, expected_output)

    def assertPrints(self, *expected_output):
        expected_output = "\n".join(expected_output) + "\n"
        return _AssertStdoutContext(self, expected_output)

    def assertWarns(self, *expected_output):
        return _AssertWarningsContext(self, expected_output)

    def assertCreatesTempFile(self, fname):
        return _AssertCreatesTempFile(self, fname)



class _AssertNotRaisesContext:

    def __init__(self, testcase, exc):
        self.testcase = testcase
        self.exc = exc

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is None:
            return # got no exception; counts as SUCCESS
        if not issubclass(exc_type, self.exc):
            return False # got the wrong type of exception, do not suppress it; counts as ERROR
        # got the right type of exception, test fails; counts as FAILURE
        self.testcase.fail("Unexpected exception: {}: {}".format(exc_type.__name__, exc_value))



class _AssertStdoutContext:

    def __init__(self, testcase, expected):
        self.testcase = testcase
        self.expected = expected
        self.captured = io.StringIO()

    def __enter__(self):
        sys.stdout = self.captured
        return self

    def __exit__(self, exc_type, exc_value, tb):
        sys.stdout = sys.__stdout__
        captured = self.captured.getvalue()
        self.testcase.assertEqual(captured, self.expected)



class _AssertStderrContext:

    def __init__(self, testcase, expected):
        self.testcase = testcase
        self.expected = expected
        self.captured = io.StringIO()

    def __enter__(self):
        sys.stderr = self.captured
        return self

    def __exit__(self, exc_type, exc_value, tb):
        sys.stderr = sys.__stderr__
        captured = self.captured.getvalue()
        self.testcase.assertEqual(captured, self.expected)



class _AssertWarningsContext:

    def __init__(self, testcase, expected):
        self.testcase = testcase
        self.expected = expected
        self.catcher = warnings.catch_warnings(record=True)

    def __enter__(self):
        self.warnings = self.catcher.__enter__()
        return self


    def __exit__(self, exc_type, exc_value, tb):
        self.catcher.__exit__(exc_type, exc_value, tb)

        testcase = self.testcase
        expected = self.expected
        warnings = self.warnings

        testcase.assertEqual(len(warnings), len(expected))
        messages = tuple(str(w.message) for w in warnings)
        testcase.assertEqual(messages, expected)



class _AssertCreatesTempFile:

    def __init__(self, testcase, fname):
        self.testcase = testcase
        self.fname = fname

    def __enter__(self):
        self.testcase.assertFalse(os.path.exists(self.fname))
        return self

    def __exit__(self, exc_type, exc_value, tb):
        fname = self.fname
        self.testcase.assertTrue(os.path.exists(fname))
        os.remove(fname)



from sfdata.utils.closedh5 import ClosedH5Error


def check_channel_closed(testcase, ch):
    with testcase.assertRaises(ClosedH5Error):
        ch.data
    with testcase.assertRaises(ClosedH5Error):
        ch.pids

    with testcase.assertRaises(ClosedH5Error):
        ch.shape
    with testcase.assertRaises(ClosedH5Error):
        ch.dtype
    with testcase.assertRaises(ClosedH5Error):
        ch.ndim
    with testcase.assertRaises(ClosedH5Error):
        ch.size



