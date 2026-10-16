"""Download privacy and reversible custom-column regression coverage."""
import csv
import io
import json
import unittest

from flask import Flask, send_file
from gurumoji.web.security import register_request_security
from gurumoji.services.speaker_registry import (
    speaker_attribute_csv_headers, speaker_registry_csv_bytes, import_speaker_registry_csv,
)


class ExportSafetyTests(unittest.TestCase):
    def test_json_file_download_is_sanitized_without_losing_attachment(self):
        app = Flask(__name__)
        register_request_security(app, remote_access_enabled=lambda: True,
            remote_access_token=lambda: "synthetic-test-token-only", remote_local_paths_enabled=lambda: False,
            max_media_upload_bytes=lambda: 1000, max_csv_upload_bytes=lambda: 1000,
            max_json_request_bytes=lambda: 1000, multipart_overhead_bytes=0,
            is_colab_runtime=lambda: False, trusted_request_hosts=lambda: {"localhost"},
            remote_auth_valid=lambda: True, request_origin_allowed=lambda _: True,
            admit_transcription_job=lambda: None, release_job_admission=lambda: None)

        @app.get('/download')
        def download():
            return send_file(io.BytesIO(json.dumps({'error': 'C:\\synthetic\\private',
                'count': 0, 'missing': None}).encode()), mimetype='application/json',
                as_attachment=True, download_name='result.json')

        response = app.test_client().get('/download')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'error': '[local path hidden]', 'count': 0, 'missing': None})
        self.assertIn('attachment', response.headers['Content-Disposition'])
        partial = app.test_client().get('/download', headers={'Range': 'bytes=0-20'})
        self.assertEqual(partial.status_code, 416)
        self.assertNotIn(b'private', partial.data)

    def test_custom_headers_are_unique_and_round_trip_reserved_names(self):
        attrs = {'氏名': 'custom-name', 'name': 'alias', '属性:氏名': 'literal', '年齢層': '40代'}
        record = dict(participant_code='P1', display_name='fixed-name', pseudonym='',
            default_role='participant', organization='', department='', job_title='',
            confidentiality_status='unknown', tags=[], notes='', active=True, attributes=attrs)
        content = speaker_registry_csv_bytes([record])
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
        row = next(reader)
        self.assertEqual(len(reader.fieldnames), len(set(reader.fieldnames)))
        self.assertEqual(row['氏名'], 'fixed-name')
        self.assertEqual(row['属性:氏名'], 'custom-name')
        captured = []
        def save(records, **options):
            captured.extend(records)
            return records, 2
        import_speaker_registry_csv(content, expected_revision=1, max_upload_bytes=10000, save_records=save)
        self.assertEqual(captured[0]['display_name'], 'fixed-name')
        self.assertEqual(captured[0]['attributes'], attrs)
        headers = speaker_attribute_csv_headers(['発話数', '属性:発話数'], ['発話数'])
        self.assertEqual(headers, {'属性:発話数': '属性:属性:発話数', '発話数': '属性:発話数'})


if __name__ == '__main__':
    unittest.main()
