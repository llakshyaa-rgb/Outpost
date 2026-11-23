import sqlite3
import unittest

from outpost_modules.systems import chunk_text, decode_candidates, ensure_uplink, rebuild_uplink, search_uplink


class OfflineSystemsTests(unittest.TestCase):
    def test_chunking_is_bounded_and_overlaps(self):
        chunks=chunk_text(("alpha " * 500) + "\n\n" + ("beta " * 500),800,100)
        self.assertGreater(len(chunks),1)
        self.assertTrue(all(len(x)<=900 for x in chunks))

    def test_decode_candidates_detects_base64_and_hex(self):
        b64=decode_candidates("SGVsbG8gZnJvbSBPVVRQT1NU")
        self.assertTrue(any(x["method"]=="Base64" and x["text"]=="Hello from OUTPOST" for x in b64))
        hx=decode_candidates("48656c6c6f")
        self.assertTrue(any(x["method"]=="Hex" and x["text"]=="Hello" for x in hx))

    def test_uplink_build_search_and_refresh(self):
        db=sqlite3.connect(":memory:")
        db.row_factory=sqlite3.Row
        db.execute("CREATE TABLE documents(id INTEGER PRIMARY KEY,path TEXT,name TEXT,content TEXT)")
        db.execute("INSERT INTO documents VALUES(1,'/docs/a.md','a.md','Offline local retrieval stores useful passages')")
        db.commit()
        result=rebuild_uplink(db)
        self.assertGreater(result["chunks_total"],0)
        hits=search_uplink(db,"offline retrieval")
        self.assertTrue(hits)
        db.execute("UPDATE documents SET content='Completely changed local archive passage' WHERE id=1")
        db.commit()
        result=rebuild_uplink(db)
        self.assertEqual(result["documents_refreshed"],1)
        self.assertTrue(search_uplink(db,"changed archive"))


if __name__=="__main__":
    unittest.main()
