# ============================================================
#  PG_SHIM — لایه‌ی سازگاریِ Mongo → PostgreSQL/Supabase
# ------------------------------------------------------------
#  این فایل یه Collection شبیه‌ِ pymongo می‌سازه (همون متدها:
#  find_one / find / update_one / insert_one / replace_one /
#  delete_one / count_documents / distinct / aggregate) ولی
#  پشتش به‌جای Mongo، از PostgreSQL (Supabase) با یه ستونِ JSONB
#  استفاده می‌کنه.
#
#  همه‌ی داکیومنت‌ها تویِ یه جدولِ واحد ذخیره می‌شن:
#     mongo_shim_store(collection TEXT, id TEXT, doc JSONB)
#  یعنی هر Mongo collection (مثلِ "players"، "boss"، ...) فقط یه
#  مقدارِ متفاوت برایِ ستونِ collection می‌شه — نیازی به ساختِ
#  جدولِ جدا برایِ هرکدوم نیست، و جدول در اولین اجرا خودش ساخته
#  می‌شه (نیازی به اجرایِ دستیِ SQL رویِ Supabase نیست).
#
#  چون بقیه‌ی کدبیس (database.py و ۳ فایلِ دیگه) دقیقاً همون
#  API قدیمیِ pymongo رو صدا می‌زنن، با سوییچ‌کردنِ get_db()
#  به این شیم، هیچ فایلِ دیگه‌ای لازم نیست تغییر کنه.
# ============================================================
import os
import json
import threading
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from psycopg2 import pool as _pg_pool

DATABASE_URL = os.getenv("DATABASE_URL", "")

_pool: Optional[_pg_pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()
_schema_ready = False


def _get_pool() -> _pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                if not DATABASE_URL:
                    raise RuntimeError(
                        "DATABASE_URL تنظیم نشده — آدرسِ اتصالِ Supabase/Postgres رو "
                        "تویِ متغیرهایِ محیطی ست کن."
                    )
                _pool = _pg_pool.ThreadedConnectionPool(
                    1, 20, DATABASE_URL, sslmode="require"
                )
                _ensure_schema()
    return _pool


def _ensure_schema():
    global _schema_ready
    if _schema_ready:
        return
    conn = _pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mongo_shim_store (
                    collection TEXT NOT NULL,
                    id TEXT NOT NULL,
                    doc JSONB NOT NULL DEFAULT '{}'::jsonb,
                    PRIMARY KEY (collection, id)
                );
                CREATE INDEX IF NOT EXISTS idx_mongo_shim_store_doc
                    ON mongo_shim_store USING GIN (doc);
                """
            )
        conn.commit()
        _schema_ready = True
    finally:
        _pool.putconn(conn)


def _conn():
    return _get_pool().getconn()


def _release(conn):
    _get_pool().putconn(conn)


def _id_to_key(v: Any) -> str:
    """هر مقدارِ _id (int/str/...) رو به یه کلیدِ متنیِ پایدار تبدیل می‌کنه."""
    return json.dumps(v, sort_keys=True, default=str)


class _Result:
    def __init__(self, matched=0, modified=0, upserted_id=None, deleted=0, inserted_id=None):
        self.matched_count = matched
        self.modified_count = modified
        self.upserted_id = upserted_id
        self.deleted_count = deleted
        self.inserted_id = inserted_id


# ────────────────────────────────────────────────────────────
#  تفسیرِ فیلترهایِ Mongo-style (فقط عملگرهایی که تویِ کدبیس
#  واقعاً استفاده شدن: $or, $exists, $gte, $lte, $lt, $gt, $ne, $in)
# ────────────────────────────────────────────────────────────
def _matches(doc: dict, filt: dict) -> bool:
    if not filt:
        return True
    for key, cond in filt.items():
        if key == "$or":
            if not any(_matches(doc, sub) for sub in cond):
                return False
            continue
        if key == "$and":
            if not all(_matches(doc, sub) for sub in cond):
                return False
            continue

        value = doc.get(key)
        if isinstance(cond, dict) and any(k.startswith("$") for k in cond.keys()):
            for op, arg in cond.items():
                if op == "$exists":
                    present = key in doc
                    if present != bool(arg):
                        return False
                elif op == "$gte":
                    if value is None or not (value >= arg):
                        return False
                elif op == "$lte":
                    if value is None or not (value <= arg):
                        return False
                elif op == "$gt":
                    if value is None or not (value > arg):
                        return False
                elif op == "$lt":
                    if value is None or not (value < arg):
                        return False
                elif op == "$ne":
                    if value == arg:
                        return False
                elif op == "$in":
                    if value not in arg:
                        return False
                else:
                    return False
        else:
            if value != cond:
                return False
    return True


def _apply_update(doc: dict, update: dict) -> dict:
    """اعمالِ عملگرهایِ $set / $inc / $addToSet / $pull / $unset رویِ یه دیکشنری."""
    new_doc = dict(doc)
    for op, fields in update.items():
        if op == "$set":
            for k, v in fields.items():
                new_doc[k] = v
        elif op == "$inc":
            for k, v in fields.items():
                new_doc[k] = new_doc.get(k, 0) + v
        elif op == "$addToSet":
            for k, v in fields.items():
                arr = list(new_doc.get(k, []))
                if v not in arr:
                    arr.append(v)
                new_doc[k] = arr
        elif op == "$pull":
            for k, v in fields.items():
                arr = list(new_doc.get(k, []))
                new_doc[k] = [x for x in arr if x != v]
        elif op == "$unset":
            for k in fields:
                new_doc.pop(k, None)
        else:
            # عملگرِ ناشناخته رو نادیده نمی‌گیریم بی‌سروصدا — خطا بده بهتره
            raise NotImplementedError(f"pg_shim: عملگرِ آپدیتِ پشتیبانی‌نشده: {op}")
    return new_doc


class Collection:
    """جایگزینِ pymongo.collection.Collection — همون امضایِ متدها."""

    def __init__(self, name: str):
        self.name = name

    # ---- کمکی‌های داخلی ----
    def _fetch_by_id(self, cur, id_key: str) -> Optional[dict]:
        cur.execute(
            "SELECT doc FROM mongo_shim_store WHERE collection=%s AND id=%s",
            (self.name, id_key),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def _fetch_all(self, cur) -> list[dict]:
        cur.execute(
            "SELECT doc FROM mongo_shim_store WHERE collection=%s", (self.name,)
        )
        return [r[0] for r in cur.fetchall()]

    def _upsert(self, cur, id_key: str, doc: dict):
        cur.execute(
            """
            INSERT INTO mongo_shim_store (collection, id, doc)
            VALUES (%s, %s, %s)
            ON CONFLICT (collection, id) DO UPDATE SET doc = EXCLUDED.doc
            """,
            (self.name, id_key, psycopg2.extras.Json(doc)),
        )

    # ---- API عمومی ----
    def find_one(self, filt: Optional[dict] = None, projection: Optional[dict] = None) -> Optional[dict]:
        filt = filt or {}
        conn = _conn()
        try:
            with conn.cursor() as cur:
                if "_id" in filt and len(filt) == 1:
                    doc = self._fetch_by_id(cur, _id_to_key(filt["_id"]))
                    return dict(doc) if doc else None
                for doc in self._fetch_all(cur):
                    if _matches(doc, filt):
                        return dict(doc)
                return None
        finally:
            _release(conn)

    def find(self, filt: Optional[dict] = None):
        filt = filt or {}
        conn = _conn()
        try:
            with conn.cursor() as cur:
                docs = self._fetch_all(cur)
            return [dict(d) for d in docs if _matches(d, filt)]
        finally:
            _release(conn)

    def insert_one(self, doc: dict):
        assert "_id" in doc, "pg_shim: insert_one نیاز به _id داره"
        conn = _conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO mongo_shim_store (collection, id, doc) VALUES (%s,%s,%s)",
                    (self.name, _id_to_key(doc["_id"]), psycopg2.extras.Json(doc)),
                )
            conn.commit()
            return _Result(inserted_id=doc["_id"])
        finally:
            _release(conn)

    def update_one(self, filt: dict, update: dict, upsert: bool = False) -> _Result:
        assert "_id" in filt, "pg_shim: update_one فعلاً فقط با فیلترِ شاملِ _id پشتیبانی می‌شه"
        id_key = _id_to_key(filt["_id"])
        extra_filt = {k: v for k, v in filt.items() if k != "_id"}
        conn = _conn()
        try:
            with conn.cursor() as cur:
                existing = self._fetch_by_id(cur, id_key)
                if existing is None:
                    if upsert:
                        base = {"_id": filt["_id"]}
                        new_doc = _apply_update(base, update)
                        new_doc["_id"] = filt["_id"]
                        self._upsert(cur, id_key, new_doc)
                        conn.commit()
                        return _Result(matched=0, modified=0, upserted_id=filt["_id"])
                    return _Result(matched=0, modified=0)

                if not _matches(existing, extra_filt):
                    return _Result(matched=0, modified=0)

                new_doc = _apply_update(existing, update)
                new_doc["_id"] = filt["_id"]
                self._upsert(cur, id_key, new_doc)
                conn.commit()
                return _Result(matched=1, modified=1)
        finally:
            _release(conn)

    def replace_one(self, filt: dict, replacement: dict, upsert: bool = False) -> _Result:
        assert "_id" in filt, "pg_shim: replace_one فعلاً فقط با فیلترِ شاملِ _id پشتیبانی می‌شه"
        id_key = _id_to_key(filt["_id"])
        conn = _conn()
        try:
            with conn.cursor() as cur:
                existing = self._fetch_by_id(cur, id_key)
                if existing is None and not upsert:
                    return _Result(matched=0, modified=0)
                new_doc = dict(replacement)
                new_doc["_id"] = filt["_id"]
                self._upsert(cur, id_key, new_doc)
            conn.commit()
            if existing is None:
                return _Result(matched=0, modified=0, upserted_id=filt["_id"])
            return _Result(matched=1, modified=1)
        finally:
            _release(conn)

    def delete_one(self, filt: dict) -> _Result:
        conn = _conn()
        try:
            with conn.cursor() as cur:
                if "_id" in filt and len(filt) == 1:
                    cur.execute(
                        "DELETE FROM mongo_shim_store WHERE collection=%s AND id=%s",
                        (self.name, _id_to_key(filt["_id"])),
                    )
                    deleted = cur.rowcount
                else:
                    docs = self._fetch_all(cur)
                    target = next((d for d in docs if _matches(d, filt)), None)
                    deleted = 0
                    if target is not None:
                        cur.execute(
                            "DELETE FROM mongo_shim_store WHERE collection=%s AND id=%s",
                            (self.name, _id_to_key(target["_id"])),
                        )
                        deleted = cur.rowcount
            conn.commit()
            return _Result(deleted=deleted)
        finally:
            _release(conn)

    def count_documents(self, filt: Optional[dict] = None) -> int:
        return len(self.find(filt or {}))

    def distinct(self, field: str, filt: Optional[dict] = None) -> list:
        docs = self.find(filt or {})
        seen = []
        for d in docs:
            v = d.get(field)
            if v not in seen:
                seen.append(v)
        return seen

    def aggregate(self, pipeline: list) -> list:
        """پشتیبانیِ یه زیرمجموعه‌ی محدود ولی کافی: $match, $group ($sum), $sort, $limit."""
        docs = self.find({})
        for stage in pipeline:
            if "$match" in stage:
                docs = [d for d in docs if _matches(d, stage["$match"])]
            elif "$group" in stage:
                grp = stage["$group"]
                group_key_expr = grp["_id"]
                buckets: dict = {}
                order = []
                for d in docs:
                    if isinstance(group_key_expr, str) and group_key_expr.startswith("$"):
                        key = d.get(group_key_expr[1:])
                    else:
                        key = group_key_expr
                    if key not in buckets:
                        buckets[key] = {"_id": key}
                        order.append(key)
                    for out_field, acc in grp.items():
                        if out_field == "_id":
                            continue
                        if "$sum" in acc:
                            arg = acc["$sum"]
                            inc = 1 if arg == 1 else d.get(str(arg).lstrip("$"), 0)
                            buckets[key][out_field] = buckets[key].get(out_field, 0) + inc
                docs = [buckets[k] for k in order]
            elif "$sort" in stage:
                for field, direction in reversed(list(stage["$sort"].items())):
                    docs.sort(key=lambda d: d.get(field), reverse=(direction < 0))
            elif "$limit" in stage:
                docs = docs[: stage["$limit"]]
        return docs


class Database:
    def __getitem__(self, name: str) -> Collection:
        return Collection(name)


def get_shim_db() -> Database:
    _get_pool()  # مطمئن شو که pool و جدول ساخته شدن
    return Database()
