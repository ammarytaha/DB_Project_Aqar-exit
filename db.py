# db.py · pip install pymysql cryptography
import os
import threading
import pymysql
from urllib.parse import urlparse, unquote

# DB_URI = the Service URI copied from Aiven. The password must not be in the code (the repo is public):
#  - on Streamlit Cloud it comes from the app's Secrets (DB_URI = "mysql://...")
#  - on your laptop it is read from the file .db_uri next to this file (that file is never uploaded)
def _db_uri():
    if os.environ.get("DB_URI"):
        return os.environ["DB_URI"]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".db_uri")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    raise RuntimeError("Set DB_URI or create the file .db_uri with the Aiven Service URI")

u = urlparse(_db_uri())

# Opening a connection to Aiven takes ~0.5 s (SSL, remote server), so each thread keeps one
# connection open and reuses it. (Streamlit runs pages in threads, and a connection can't be shared.)
_local = threading.local()

def _connection():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _local.conn = pymysql.connect(
            host=u.hostname, port=u.port, database=u.path[1:],
            user=u.username, password=unquote(u.password))
    else:
        conn.ping(reconnect=True)      # reconnect if Aiven closed the idle connection
    return conn

def run(sql, params=None):
    conn = _connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.commit()          # save INSERT / UPDATE / DELETE (harmless for SELECT)
    cur.close()
    return rows

