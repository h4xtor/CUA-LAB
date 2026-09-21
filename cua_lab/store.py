import json
import os
import platform
import sqlite3
import time
from pathlib import Path
from .privacy import redact

def data_dir():
    return Path(os.getenv('CUA_LAB_DATA_DIR') or (Path(os.getenv('LOCALAPPDATA', Path.home() / '.local/share')) / 'CUA-LAB'))

class Store:
    def __init__(self, root=None):
        self.root = Path(root) if root else data_dir()
        for folder in ('database','logs','sessions','machine','cache','pending-memory'):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        # Constructed before the native GUI launches its backend thread. All
        # subsequent calls are synchronous on that single backend event loop.
        self.db = sqlite3.connect(self.root / 'database/cua-lab.sqlite3', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, prompt TEXT, machine TEXT, started REAL, ended REAL, status TEXT, metadata TEXT);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT, timestamp REAL, step INTEGER, type TEXT, data TEXT);
        CREATE TABLE IF NOT EXISTS learnings(id TEXT PRIMARY KEY, data TEXT, synced INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        ''')
        self.db.execute("UPDATE sessions SET status='interrupted', ended=? WHERE ended IS NULL", (time.time(),))
        self.db.commit()

    def create(self, sid, prompt, metadata):
        self.db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)', (sid, redact(prompt), platform.node(), time.time(), None, 'running', json.dumps(metadata)))
        self.db.commit()

    def finish(self, sid, status):
        self.db.execute('UPDATE sessions SET status=?,ended=? WHERE id=?', (status,time.time(),sid))
        self.db.commit()

    def event(self, sid, step, kind, data):
        data = redact(data)
        now = time.time()
        cur = self.db.execute('INSERT INTO events(session,timestamp,step,type,data) VALUES(?,?,?,?,?)', (sid,now,step,kind,json.dumps(data,ensure_ascii=False)))
        self.db.commit()
        return dict(id=cur.lastrowid,session=sid,timestamp=now,step=step,type=kind,data=data)

    def sessions(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM sessions ORDER BY started DESC LIMIT 100')]

    def events(self, sid):
        return [{**dict(r), 'data': json.loads(r['data'])} for r in self.db.execute('SELECT * FROM events WHERE session=? ORDER BY id', (sid,))]

    def save_learning(self, record, synced=False):
        self.db.execute('INSERT INTO learnings VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,synced=excluded.synced', (record.id,record.model_dump_json(),int(synced)))
        self.db.commit()

    def learnings(self):
        return [{**json.loads(r['data']), 'synced': bool(r['synced'])} for r in self.db.execute('SELECT * FROM learnings ORDER BY id')]

    def close(self):
        self.db.close()
