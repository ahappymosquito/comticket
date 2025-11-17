import sqlite3
from loguru import logger
from contextlib import contextmanager


class SQLiteDB:
    def __init__(self, path="info_monitor.db"):
        self.path = path
        self.conn = None

    def connect(self):
        if self.conn:
            return self.conn

        logger.info(f"连接 SQLite 数据库: {self.path}")
        self.conn = sqlite3.connect(self.path)

        # sqlite3.Row 能让你像 dict 一样通过 key 访问字段
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        if self.conn:
            logger.info("关闭 SQLite 连接")
            self.conn.close()
            self.conn = None

    @contextmanager
    def cursor(self):
        """上下文管理游标，自动提交和异常回滚"""
        conn = self.connect()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"SQLite 执行异常: {e}")
            raise
        finally:
            cur.close()

    def execute(self, sql, params=None):
        params = params or ()
        with self.cursor() as cur:
            logger.debug(f"SQL 执行：{sql} | params={params}")
            cur.execute(sql, params)
            return cur.rowcount

    def query_one(self, sql, params=None):
        params = params or ()
        with self.cursor() as cur:
            logger.debug(f"SQL 查询一行：{sql} | params={params}")
            cur.execute(sql, params)
            return cur.fetchone()

    def query_all(self, sql, params=None):
        params = params or ()
        with self.cursor() as cur:
            logger.debug(f"SQL 查询多行：{sql} | params={params}")
            cur.execute(sql, params)
            return cur.fetchall()

    def executemany(self, sql, seq):
        """批量插入或批量执行"""
        with self.cursor() as cur:
            logger.debug(f"批量执行 SQL：{sql} | count={len(seq)}")
            cur.executemany(sql, seq)

    def vacuum(self):
        """清理数据库文件碎片"""
        logger.info("执行 VACUUM 清理数据库空间")
        self.execute("VACUUM;")


if __name__ == '__main__':
    # ---------------------------------------------------------
    # 以下为你监控需求使用的“业务逻辑层”，基于上面的 SQLite 封装
    # ---------------------------------------------------------

    def create_table(db: SQLiteDB):
        sql = """
        CREATE TABLE IF NOT EXISTS info (
            version TEXT,
            issue_description TEXT,
            author TEXT,
            timestamp TEXT
        );
        """
        db.execute(sql)


    def get_last_info(db: SQLiteDB):
        sql = "SELECT * FROM info ORDER BY rowid DESC LIMIT 1;"
        return db.query_one(sql)


    def save_info(db: SQLiteDB, info):
        sql = "INSERT INTO info VALUES (?, ?, ?, ?);"
        db.execute(sql, info)
