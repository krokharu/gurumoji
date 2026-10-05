"""CSV initialization must fit the platform and retain long saved fields."""
import csv
import io
import sys
import unittest
from unittest.mock import patch

from gurumoji.handlers import analysis_queries


class CsvFieldLimitTests(unittest.TestCase):
    def test_narrow_c_long_fallback_still_reads_long_saved_cell(self):
        real_set_limit = csv.field_size_limit
        previous = real_set_limit()
        attempts = []

        def narrow_limit(value):
            attempts.append(value)
            if value > 2**31 - 1:
                raise OverflowError("simulated Windows C long")
            return real_set_limit(value)

        try:
            with patch.object(analysis_queries.csv, "field_size_limit", side_effect=narrow_limit):
                selected = analysis_queries._configure_csv_field_limit()
            self.assertEqual(attempts[0], sys.maxsize)
            self.assertLessEqual(selected, 2**31 - 1)
            text = "長い保存セル" * 40000
            rows = list(csv.reader(io.StringIO('"' + text + '"\n')))
            self.assertEqual(rows, [[text]])
        finally:
            real_set_limit(previous)
