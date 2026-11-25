import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from github_models.panel_export import SCHEMA, SECTIONS, decode, digest, encode, verify

class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'bundle.zip'
        self.payload = {s+'.json': b'{}' for s in SECTIONS}
        self.manifest = {'schema': SCHEMA, 'forecast_cutoff_utc':'2026-11-24T12:00:00Z', 'audit_as_of_utc':'2026-11-25T12:00:00Z', 'files': {k:{'sha256':digest(v),'bytes':len(v)} for k,v in self.payload.items()}}

    def write(self):
        with ZipFile(self.path,'w') as z:
            for k,v in self.payload.items(): z.writestr(k,v)
            z.writestr('MANIFEST.json',encode(self.manifest))

    def test_valid(self):
        self.write(); self.assertEqual(verify(self.path),self.manifest)

    def test_tamper(self):
        self.payload['FIXTURES.json']=b'{ }'; self.write()
        with self.assertRaisesRegex(ValueError,'bundle_integrity'): verify(self.path)

    def test_unknown_file(self):
        self.payload['unknown.json']=b'{}'; self.write()
        with self.assertRaisesRegex(ValueError,'unexpected_bundle_files'): verify(self.path)

    def test_schema(self):
        self.manifest['schema']='unknown'; self.write()
        with self.assertRaisesRegex(ValueError,'unsupported_bundle_schema'): verify(self.path)

    def test_forecast_rollback(self):
        self.write()
        with self.assertRaisesRegex(ValueError,'older_snapshot:forecast_cutoff_utc'): verify(self.path,{**self.manifest,'forecast_cutoff_utc':'2026-11-26T12:00:00Z'})

    def test_audit_rollback(self):
        self.write()
        with self.assertRaisesRegex(ValueError,'older_snapshot:audit_as_of_utc'): verify(self.path,{**self.manifest,'audit_as_of_utc':'2026-11-26T12:00:00Z'})

    def test_same_cutoff_conflict(self):
        self.write()
        previous={**self.manifest,'files':{}}
        with self.assertRaisesRegex(ValueError,'same_cutoff_conflicting_payload'): verify(self.path,previous)

    def test_same_cutoff_identical(self):
        self.write()
        self.assertEqual(verify(self.path,self.manifest),self.manifest)

    def test_duplicate_key(self):
        with self.assertRaisesRegex(ValueError,'duplicate_json_key'): decode(b'{"a":1,"a":2}')

    def test_nonfinite(self):
        with self.assertRaisesRegex(ValueError,'nonfinite_json'): decode(b'{"a":NaN}')

if __name__=='__main__': unittest.main()
