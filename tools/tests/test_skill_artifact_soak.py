"""The repeat harness must not convert partial pytest runs into acceptance."""

import tempfile
import unittest
from pathlib import Path

from tools.entrypoints.skill_artifact_soak import report_counts


class ReportCountsTests(unittest.TestCase):
    def count(self, xml):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.xml'
            path.write_text(xml)
            return report_counts(path)

    def test_nested_suites_count_cases_once(self):
        self.assertEqual(
            self.count('<testsuites tests="2"><testsuite tests="2"><testcase/><testcase/></testsuite></testsuites>'),
            {'tests': 2, 'failures': 0, 'errors': 0, 'skipped': 0},
        )

    def test_skips_and_failures_remain_visible(self):
        counts = self.count(
            '<testsuite><testcase><skipped type="pytest.xfail"/></testcase>'
            '<testcase><failure/></testcase><testcase><error/></testcase></testsuite>'
        )
        self.assertEqual(counts, {'tests': 3, 'failures': 1, 'errors': 1, 'skipped': 1})

    def test_empty_report_has_no_tests(self):
        self.assertEqual(self.count('<testsuites/>')['tests'], 0)


if __name__ == '__main__':
    unittest.main()
