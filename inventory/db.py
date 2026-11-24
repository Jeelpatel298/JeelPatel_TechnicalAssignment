from contextlib import contextmanager

import pymysql
from flask import current_app, g
from pymysql.cursors import DictCursor


def connection():
    if "db" not in g:
        g.db = pymysql.connect(
            **current_app.config["DATABASE"],
            autocommit=True,
            charset="utf8mb4",
            cursorclass=DictCursor,
            connect_timeout=5,
            init_command="SET time_zone = '+00:00'",
        )
    return g.db


def close(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@contextmanager
def transaction():
    db = connection()
    db.begin()
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


def query(sql, args=(), *, one=False):
    with connection().cursor() as cursor:
        cursor.execute(sql, args)
        return cursor.fetchone() if one else list(cursor.fetchall())


def execute(sql, args=()):
    with connection().cursor() as cursor:
        cursor.execute(sql, args)
        return cursor.lastrowid
