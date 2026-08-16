#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""春水池 SQLite 数据层"""
import sqlite3, os, datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  nickname       TEXT NOT NULL,
  password       TEXT NOT NULL,
  email          TEXT NOT NULL UNIQUE,
  email_password TEXT,
  user_id        TEXT,
  registered_at  TEXT,                -- aimagnet createdAt (unix 秒)
  imported_at    TEXT DEFAULT (datetime('now','localtime')),
  petals         INTEGER DEFAULT 0,   -- 当前花瓣
  last_sign_date TEXT,                -- 最近签到日 YYYY-MM-DD
  last_sign_at   TEXT,                -- 最近签到时间
  status         TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS sign_records (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER NOT NULL,
  date       TEXT NOT NULL,
  status     TEXT NOT NULL,           -- SIGNED/ALREADY/ERROR
  reward     INTEGER,
  error      TEXT,
  created_at TEXT DEFAULT (datetime('now','localtime')),
  UNIQUE(account_id, date)
);
CREATE TABLE IF NOT EXISTS point_snapshots (
  account_id INTEGER NOT NULL,
  date       TEXT NOT NULL,
  points     INTEGER NOT NULL,
  UNIQUE(account_id, date)
);
CREATE INDEX IF NOT EXISTS idx_sign_account ON sign_records(account_id, date);
CREATE INDEX IF NOT EXISTS idx_point_account ON point_snapshots(account_id, date);
"""

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = conn(); c.executescript(SCHEMA); c.commit(); c.close()

def add_account(nickname, password, email, email_password, user_id, registered_at, petals=0):
    c = conn()
    try:
        c.execute("""INSERT OR IGNORE INTO accounts(nickname,password,email,email_password,user_id,registered_at,petals)
                     VALUES(?,?,?,?,?,?,?)""",
                  (nickname, password, email, email_password, user_id, registered_at, petals))
        c.commit()
        return c.total_changes > 0
    finally:
        c.close()

def accounts(status=None):
    c = conn()
    q = "SELECT * FROM accounts"
    p = ()
    if status:
        q += " WHERE status=?"; p = (status,)
    rows = c.execute(q + " ORDER BY id", p).fetchall()
    c.close(); return rows

def get_account(aid):
    c = conn(); r = c.execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone(); c.close(); return r

def update_account(aid, **kw):
    if not kw: return
    cols = ", ".join(f"{k}=?" for k in kw)
    c = conn(); c.execute(f"UPDATE accounts SET {cols} WHERE id=?", (*kw.values(), aid)); c.commit(); c.close()

def record_sign(aid, date, status, reward=None, error=None):
    c = conn()
    c.execute("""INSERT OR REPLACE INTO sign_records(account_id,date,status,reward,error,created_at)
                 VALUES(?,?,?,?,?,datetime('now','localtime'))""",
              (aid, date, status, reward, error))
    c.commit(); c.close()

def record_point(aid, date, points):
    c = conn()
    c.execute("INSERT OR REPLACE INTO point_snapshots(account_id,date,points) VALUES(?,?,?)", (aid, date, points))
    c.commit(); c.close()

def sign_history(aid, limit=60):
    c = conn()
    rows = c.execute("SELECT * FROM sign_records WHERE account_id=? ORDER BY date DESC LIMIT ?", (aid, limit)).fetchall()
    c.close(); return rows

def point_history(aid, limit=90):
    c = conn()
    rows = c.execute("SELECT * FROM point_snapshots WHERE account_id=? ORDER BY date DESC LIMIT ?", (aid, limit)).fetchall()
    c.close(); return rows

def today_str():
    return datetime.date.today().isoformat()