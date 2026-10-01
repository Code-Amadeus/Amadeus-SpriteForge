"""JSON handle/replace ownership, without retries or timing-dependent races."""
import threading
from pathlib import Path

from spriteforge import workspace


def test_json_replace_waits_for_reader_handle_and_preserves_complete_snapshots(tmp_path,monkeypatch):
    path=tmp_path/"run.json"
    old={"state":"旧状态","items":list(range(16))}
    new={"state":"新状态","items":list(range(32))}
    workspace.atomic_json(path,old)
    reader_opened=threading.Event()
    reader_closed=threading.Event()
    release_reader=threading.Event()
    writer_waiting=threading.Event()
    replace_entered=threading.Event()
    writer_done=threading.Event()
    original_read=Path.read_text
    original_replace=workspace.os.replace
    lock=threading.Lock()
    results={}

    class ObservedLock:
        def __enter__(self):
            if threading.current_thread().name=="json-writer":
                writer_waiting.set()
            lock.acquire()
            return self
        def __exit__(self,*_):
            lock.release()

    def held_read(self,*args,**kwargs):
        if self!=path or threading.current_thread().name!="json-reader":
            return original_read(self,*args,**kwargs)
        with self.open(mode="r",encoding=kwargs["encoding"]) as stream:
            reader_opened.set()
            if not release_reader.wait(5):
                raise TimeoutError("Reader was not released")
            content=stream.read()
        reader_closed.set()
        return content

    def observed_replace(source,target):
        results["replace_calls"]=results.get("replace_calls",0)+1
        replace_entered.set()
        assert reader_closed.is_set(),"Replace entered while the reader handle was still open"
        return original_replace(source,target)

    def reader():
        try:results["read"]=workspace.read_json(path)
        except BaseException as error:results["read_error"]=error

    def writer():
        try:workspace.atomic_json(path,new)
        except BaseException as error:results["write_error"]=error
        finally:writer_done.set()

    monkeypatch.setattr(workspace,"_JSON_IO_LOCK",ObservedLock())
    monkeypatch.setattr(Path,"read_text",held_read)
    monkeypatch.setattr(workspace.os,"replace",observed_replace)
    read_thread=threading.Thread(target=reader,name="json-reader",daemon=True)
    write_thread=threading.Thread(target=writer,name="json-writer",daemon=True)
    read_thread.start()
    try:
        assert reader_opened.wait(5)
        write_thread.start()
        assert writer_waiting.wait(5),"Writer did not reach the replace boundary"
        assert not replace_entered.is_set()
        assert not writer_done.is_set()
        release_reader.set()
        read_thread.join(5)
        write_thread.join(5)
        assert not read_thread.is_alive() and not write_thread.is_alive()
        assert "read_error" not in results and "write_error" not in results,results
        assert results["read"]==old
        assert workspace.read_json(path)==new
        assert results["replace_calls"]==1
        assert not list(tmp_path.glob(".run.json.*.tmp"))
    finally:
        release_reader.set()
        read_thread.join(5)
        if write_thread.ident is not None:
            write_thread.join(5)
