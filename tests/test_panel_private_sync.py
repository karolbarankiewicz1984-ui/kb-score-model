import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from github_models.panel_export import digest,encode,SECTIONS,SCHEMA
from tools.panel_prepare import select,ROLES
from tools.panel_publish import publish,check,KEY

def make(path, cutoff="2026-11-24T12:00:00Z", audit="2026-11-25T12:00:00Z", payload=None):
    sections={s+".json":encode(payload or {}) for s in SECTIONS}
    manifest={"schema":SCHEMA,"forecast_cutoff_utc":cutoff,"audit_as_of_utc":audit,
              "publication":"local_only","historical_snapshot":True,
              "sources":{r:{"run_id":i+1} for i,r in enumerate(("abc","odds","audit"))},
              "files":{k:{"sha256":digest(v),"bytes":len(v)} for k,v in sections.items()}}
    with ZipFile(path,"w") as z:
        for k,v in sections.items():z.writestr(k,v)
        z.writestr("MANIFEST.json",encode(manifest))
    return path

class Missing(Exception):
    response={"Error":{"Code":"NoSuchKey"}}
class Storage:
    def __init__(self, old=None, fail=False):
        self.old=old;self.fail=fail;self.puts=[]
    def get_object(self,**kwargs):
        if self.old is None:raise Missing()
        return {"Body":io.BytesIO(self.old),"ContentLength":len(self.old),"ETag":'"old"'}
    def put_object(self,**kwargs):
        if self.fail:raise RuntimeError("precondition_failed")
        self.puts.append({k:v for k,v in kwargs.items() if k!="Body"})
        self.old=kwargs["Body"].read()

class PrivateSync(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.old=make(self.root/"old.zip")
    def test_new_publish_is_conditional(self):
        s=Storage();self.assertEqual(publish(s,"test",self.old),"published")
        self.assertEqual(s.puts[0]["IfNoneMatch"],"*");self.assertEqual(s.puts[0]["Key"],KEY)
    def test_newer_replacement_is_conditional(self):
        s=Storage(self.old.read_bytes());new=make(self.root/"new.zip",audit="2026-11-26T12:00:00Z")
        self.assertEqual(publish(s,"test",new),"published");self.assertEqual(s.puts[0]["IfMatch"],'"old"')
    def test_same_snapshot_no_write(self):
        s=Storage(self.old.read_bytes());self.assertEqual(publish(s,"test",self.old),"unchanged");self.assertFalse(s.puts)
    def test_older_or_same_cutoff_conflict_no_write(self):
        s=Storage(self.old.read_bytes())
        for path in [make(self.root/"older.zip",audit="2026-11-24T12:00:00Z"),make(self.root/"conflict.zip",payload={"different":1})]:
            with self.assertRaises(ValueError):publish(s,"test",path)
        self.assertFalse(s.puts)
    def test_concurrent_precondition_is_not_retried(self):
        s=Storage(self.old.read_bytes(),fail=True);new=make(self.root/"new.zip",audit="2026-11-26T12:00:00Z")
        with self.assertRaisesRegex(RuntimeError,"precondition_failed"):publish(s,"test",new)
        self.assertEqual(s.old,self.old.read_bytes())
    def test_corrupt_previous_stops_publish(self):
        s=Storage(b"broken")
        with self.assertRaises(Exception):publish(s,"test",self.old)
        self.assertFalse(s.puts)
    def test_select_only_successful_exact_artifact(self):
        run={"id":123,"run_attempt":2,"path":ROLES["abc"][0],"head_branch":"main","status":"completed","conclusion":"success"}
        artifact={"id":1,"name":"github-models-v2-abc-complete-123-2","expired":False,"size_in_bytes":10}
        self.assertEqual(select("abc",run,[artifact]),artifact)
        for wrong in [{**run,"conclusion":"failure"},{**run,"head_branch":"other"},{**run,"path":"other"}]:
            with self.assertRaises(ValueError):select("abc",wrong,[artifact])
        for bad in [[],[artifact,artifact],[{**artifact,"expired":True}],[{**artifact,"name":"github-models-v2-abc-complete-123-1"}]]:
            with self.assertRaises(ValueError):select("abc",run,bad)
if __name__=="__main__":unittest.main()
