"""Native exported files reopen with fixed values and provenance."""
import io
import json
import tempfile
import unittest
from pathlib import Path
import zipfile

from openpyxl import load_workbook
from gurumoji.services.fixed_exports import workbook_bytes, sav_bundle, image_bytes


class FixedExportsTests(unittest.TestCase):
    def setUp(self):
        self.table = {'fields': ['name', 'value'], 'rows': [
            {'row_id': 'r1', 'values': {'name': '=1+1', 'value': 0}},
            {'row_id': 'r2', 'values': {'name': '日本語', 'value': None}},
            {'row_id': 'r3', 'values': {'name': '', 'value': -2}},
        ]}
        self.provenance = {'run_id': 'synthetic', 'snapshot_id': 'fixed', 'input_hash': 'hash'}

    def test_excel_preserves_numbers_missing_state_and_formula_safety(self):
        book = load_workbook(io.BytesIO(workbook_bytes({'values': self.table}, self.provenance)))
        self.assertEqual(book['values']['B2'].value, 0)
        self.assertEqual(book['values']['B4'].value, -2)
        self.assertNotEqual(book['values']['A2'].data_type, 'f')
        self.assertEqual(book['_missing']['D2'].value, 'null')
        self.assertEqual(book['_missing']['D3'].value, 'empty_string')
        self.assertIn('synthetic', book['README']['B1'].value)

    def test_sav_reopens_and_typed_sidecar_retains_missingness(self):
        import pyreadstat
        data = sav_bundle({'values': self.table}, self.provenance)
        with zipfile.ZipFile(io.BytesIO(data)) as archive, tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'values.sav'
            path.write_bytes(archive.read('values.sav'))
            frame, metadata = pyreadstat.read_sav(str(path))
            self.assertEqual(frame.iloc[0, 1], 0)
            self.assertEqual(frame.iloc[2, 1], -2)
            self.assertEqual(metadata.column_labels, ['name', 'value'])
            self.assertEqual(json.loads(archive.read('values.typed.json')), self.table)

    def test_images_escape_text_and_include_fixed_run(self):
        svg = image_bytes(self.table, '<values>', self.provenance, 'svg').decode()
        self.assertIn('&lt;values&gt;', svg)
        self.assertIn('synthetic', svg)
        self.assertIn('欠測', svg)
        from PIL import Image
        image = Image.open(io.BytesIO(image_bytes(self.table, 'values', self.provenance, 'png')))
        self.assertEqual(image.format, 'PNG')
        self.assertEqual(image.width, 1000)
