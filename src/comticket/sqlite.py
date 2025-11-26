import sqlite3
import os
import hashlib
from loguru import logger
from contextlib import contextmanager


# ===========================
# 1. 基础数据库工具类 (通用层)
# ===========================
class SQLiteDB:
    def __init__(self, db_name="info_monitor.db", data_dir="data"):
        # 优雅处理：自动检测并创建 data 目录
        self.db_path = os.path.join(data_dir, db_name)
        self._ensure_dir(data_dir)
        self.conn = None

    def _ensure_dir(self, path):
        if not os.path.exists(path):
            os.makedirs(path)
            logger.info(f"自动创建数据目录: {path}")

    def connect(self):
        if self.conn:
            return self.conn

        # check_same_thread=False 允许在多线程环境下使用（简单场景）
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 结果以字典形式访问
        return self.conn

    def close(self):
        if self.conn:
            logger.info("关闭 SQLite 连接")
            self.conn.close()
            self.conn = None

    @contextmanager
    def cursor(self):
        """上下文管理器：自动提交事务，失败自动回滚"""
        conn = self.connect()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库执行异常: {e}")
            raise
        finally:
            cur.close()

    def execute(self, sql, params=None):
        params = params or ()
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def query_one(self, sql, params=None):
        params = params or ()
        with self.cursor() as cur:
            cur.execute(sql, params)
            result = cur.fetchone()
            return dict(result) if result else None

    def query_all(self, sql, params=None):
        params = params or ()
        with self.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


# ===========================
# 2. 业务逻辑层 (字段封装)
# ===========================

def generate_target_hash(component_name, version, mark, name, date):
    """
    根据业务字段计算唯一的 target_hash
    """
    # 将所有字段拼接成字符串进行 hash，确保唯一性
    raw_str = f"{component_name}|{version}|{mark}|{name}|{date}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()


def init_table(db: SQLiteDB):
    """初始化表结构"""
    sql = """
          CREATE TABLE IF NOT EXISTS monitor_records \
          ( \
              id \
              INTEGER \
              PRIMARY \
              KEY \
              AUTOINCREMENT, \
              component_name \
              TEXT, \
              version \
              TEXT, \
              mark \
              TEXT, \
              name \
              TEXT, \
              date \
              TEXT, \
              target_hash \
              TEXT \
              UNIQUE
          ); \
          """
    db.execute(sql)


# --- 增 (Create) ---
def add_record(db: SQLiteDB, component_name, version, mark, name, date):
    """
    添加记录。
    会自动计算 target_hash。
    如果 target_hash 已存在，则忽略插入 (INSERT OR IGNORE)。
    """
    # 1. 计算哈希
    target_hash = generate_target_hash(component_name, version, mark, name, date)

    # 2. 执行插入
    sql = """
          INSERT \
          OR IGNORE INTO monitor_records 
    (component_name, version, mark, name, date, target_hash) 
    VALUES (?, ?, ?, ?, ?, ?); \
          """
    row_count = db.execute(sql, (component_name, version, mark, name, date, target_hash))

    if row_count > 0:
        logger.success(f"新增记录成功 | Component: {component_name} | Hash: {target_hash[:8]}")
    else:
        logger.warning(f"记录已存在，跳过 | Hash: {target_hash[:8]}")
        return False

    return target_hash


# --- 删 (Delete) ---
def delete_by_hash(db: SQLiteDB, target_hash):
    """根据 target_hash 删除记录"""
    sql = "DELETE FROM monitor_records WHERE target_hash = ?;"
    count = db.execute(sql, (target_hash,))
    if count > 0:
        logger.info(f"删除成功: {target_hash}")
    else:
        logger.warning(f"删除失败，未找到 Hash: {target_hash}")


# --- 查 (Read) ---
def query_by_hash(db: SQLiteDB, target_hash):
    """查询单条记录"""
    sql = "SELECT * FROM monitor_records WHERE target_hash = ?;"
    return db.query_one(sql, (target_hash,))


def query_all_records(db: SQLiteDB):
    """查询所有记录，按 ID 倒序排列"""
    sql = "SELECT * FROM monitor_records ORDER BY id DESC;"
    return db.query_all(sql)


# ===========================
# 3. 运行测试
# ===========================
if __name__ == '__main__':
    # 初始化数据库对象
    db = SQLiteDB()

    # 初始化表
    init_table(db)

    # 模拟数据
    sample_data = {
        "component_name": "UserModule",
        "version": "3.3.9",
        "mark": "修复账户信息同步问题",
        "name": "许敬东",
        "date": "2025年11月26日 21:58"
    }

    logger.info("--- 开始测试 ---")

    # 1. 保存数据
    saved_hash = add_record(
        db,
        sample_data['component_name'],
        sample_data['version'],
        sample_data['mark'],
        sample_data['name'],
        sample_data['date']
    )

    # 2. 测试重复保存 (应该被拦截)
    add_record(
        db,
        sample_data['component_name'],
        sample_data['version'],
        sample_data['mark'],
        sample_data['name'],
        sample_data['date']
    )

    # 3. 查询刚刚保存的数据
    record = query_by_hash(db, saved_hash)
    if record:
        logger.info(f"查找到数据: {record}")

    # 4. 列出所有数据
    all_data = query_all_records(db)
    print(f"\n当前数据库共有 {len(all_data)} 条记录:")
    for row in all_data:
        print(f" - [{row['date']}] {row['component_name']} ({row['version']}) - Hash:{row['target_hash'][:6]}")

    # 5. 删除测试 (可选)
    # delete_by_hash(db, saved_hash)

    db.close()