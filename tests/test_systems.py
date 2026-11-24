import sqlite3
import unittest

from outpost_modules.systems import (chunk_text, decode_candidates, ensure_uplink, rebuild_uplink, search_uplink, record_uplink_feedback, evaluate_uplink_query, queue_uplink_question, list_uplink_questions, close_uplink_question, uplink_report)


class OfflineSystemsTests(unittest.TestCase):
    def test_chunking_is_bounded_and_overlaps(self):
        chunks=chunk_text(("alpha " * 500) + "\n\n" + ("beta " * 500),800,100)
        self.assertGreater(len(chunks),1)
        self.assertTrue(all(len(x)<=800 for x in chunks))
        long_chunks=chunk_text("x"*1900,800,100)
        self.assertTrue(all(len(x)<=800 for x in long_chunks))
        self.assertEqual(long_chunks[0][-100:],long_chunks[1][:100])
        paragraph_chunks=chunk_text(("a"*800)+"\n\n"+("b"*800),800,100)
        self.assertTrue(all(len(x)<=800 for x in paragraph_chunks))

    def test_uplink_refresh_removes_stale_passages_and_updates_source_metadata(self):
        db=sqlite3.connect(":memory:")
        db.row_factory=sqlite3.Row
        db.execute("CREATE TABLE documents(id INTEGER PRIMARY KEY,path TEXT,name TEXT,content TEXT)")
        db.execute("INSERT INTO documents VALUES(1,'/docs/old.md','old.md','A useful offline passage')")
        db.commit()
        rebuild_uplink(db)
        db.execute("UPDATE documents SET path='/docs/renamed.md',name='renamed.md' WHERE id=1")
        db.commit()
        rebuild_uplink(db)
        self.assertEqual(search_uplink(db,"offline passage")[0]["path"],"/docs/renamed.md")
        db.execute("UPDATE documents SET content='' WHERE id=1")
        db.commit()
        result=rebuild_uplink(db)
        self.assertEqual(result["chunks_total"],0)
        self.assertEqual(search_uplink(db,"offline passage"),[])

    def test_uplink_chunk_limit_does_not_replace_existing_passages(self):
        db=sqlite3.connect(":memory:")
        db.row_factory=sqlite3.Row
        db.execute("CREATE TABLE documents(id INTEGER PRIMARY KEY,path TEXT,name TEXT,content TEXT)")
        db.execute("INSERT INTO documents VALUES(1,'/docs/a.md','a.md','Short original passage')")
        db.commit()
        rebuild_uplink(db,max_chunks=10)
        original=search_uplink(db,"original passage")[0]["snippet"]
        db.execute("UPDATE documents SET content=? WHERE id=1",("new content " * 1000,))
        db.commit()
        result=rebuild_uplink(db,max_chunks=1)
        self.assertGreater(result["skipped"],0)
        self.assertEqual(search_uplink(db,"original passage")[0]["snippet"],original)

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
        hit=search_uplink(db,"changed archive")[0]
        record_uplink_feedback(db,"changed archive",hit["id"],True,"correct source")
        self.assertGreaterEqual(search_uplink(db,"changed archive")[0]["helpful_votes"],1)
        evaluation=evaluate_uplink_query(db,"changed archive","/docs/a.md")
        self.assertTrue(evaluation["matched"])
        qid=queue_uplink_question(db,"How does local archive search work?")
        self.assertEqual(list_uplink_questions(db)[0]["id"],qid)
        close_uplink_question(db,qid,"Reviewed the local index docs")
        self.assertEqual(list_uplink_questions(db)[0]["status"],"resolved")
        report=uplink_report(db)
        self.assertEqual(report["evaluation_runs"],1)
        self.assertEqual(report["questions_open"],0)



if __name__=="__main__":
    unittest.main()
