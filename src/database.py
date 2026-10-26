"""Database connection and ORM models for E-Commerce Data Warehouse."""

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

# Dam bao in tieng Viet tren Windows cmd/powershell khong bi UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Tu dong tai bien moi truong tu .env neu co python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==============================================================================
# CAU HINH KET NOI CO SO DU LIEU
# ==============================================================================

POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password123")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ecommerce_dwh")

# Uu tien DATABASE_URL neu duoc cau hinh truc tiep
DEFAULT_DB_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# Khoi tao SQLAlchemy Engine voi connection pool (ho tro fallback neu server offline)
try:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )
    with engine.connect() as _test_conn:
        _test_conn.execute(text("SELECT 1;"))
except Exception:
    project_root = Path(__file__).resolve().parent.parent
    fallback_db_path = project_root / "data" / "ecommerce_dwh.db"
    DATABASE_URL = f"sqlite:///{fallback_db_path}"
    engine = create_engine(DATABASE_URL, echo=False)

# Factory tao database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base cho các bảng ORM
Base = declarative_base()


# ==============================================================================
# ĐỊNH NGHĨA ORM MODELS THEO STAR SCHEMA
# ==============================================================================


class DimCategory(Base):
    """Bảng chiều danh mục."""

    __tablename__ = "dim_category"

    category_id = Column(String(100), primary_key=True, index=True)
    category_name = Column(String(255), nullable=False)

    products = relationship("DimProduct", back_populates="category")


class DimUser(Base):
    """Bảng chiều người dùng (Amazon ReviewerID + DummyJSON)."""

    __tablename__ = "dim_user"

    user_id = Column(String(100), primary_key=True, index=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    city = Column(String(150), nullable=True)
    country = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=True)
    rfm_segment = Column(String(50), default="Unassigned")

    interactions = relationship("FactInteraction", back_populates="user")


class DimProduct(Base):
    """Bảng chiều sản phẩm (Amazon Metadata + Open Food Facts)."""

    __tablename__ = "dim_product"

    product_id = Column(String(100), primary_key=True, index=True)
    product_name = Column(Text, nullable=False)
    category_id = Column(
        String(100), ForeignKey("dim_category.category_id"), nullable=True, index=True
    )
    price = Column(Numeric(12, 2), default=0.00)
    brand = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    ingredients_text = Column(Text, nullable=True)

    category = relationship("DimCategory", back_populates="products")
    interactions = relationship("FactInteraction", back_populates="product")


class DimTime(Base):
    """Bảng chiều thời gian."""

    __tablename__ = "dim_time"

    time_id = Column(BigInteger, primary_key=True, index=True)
    full_timestamp = Column(DateTime, nullable=False)
    day = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    day_of_week = Column(String(20), nullable=False)

    interactions = relationship("FactInteraction", back_populates="time")


class FactInteraction(Base):
    """Bảng sự kiện tương tác và đánh giá."""

    __tablename__ = "fact_interactions"

    interaction_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    user_id = Column(
        String(100), ForeignKey("dim_user.user_id"), nullable=False, index=True
    )
    product_id = Column(
        String(100), ForeignKey("dim_product.product_id"), nullable=False, index=True
    )
    time_id = Column(
        BigInteger, ForeignKey("dim_time.time_id"), nullable=False, index=True
    )
    rating_score = Column(Numeric(3, 2), nullable=True)
    review_text = Column(Text, nullable=True)
    helpful_vote = Column(Integer, default=0)
    event_type = Column(String(50), default="review", index=True)

    user = relationship("DimUser", back_populates="interactions")
    product = relationship("DimProduct", back_populates="interactions")
    time = relationship("DimTime", back_populates="interactions")


# ==============================================================================
# HÀM TIỆN ÍCH QUẢN LÝ KẾT NỐI & KHỞI TẠO DWH
# ==============================================================================


def get_db() -> Generator:
    """Dependency generator cho FastAPI để inject database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager để sử dụng trong các script ETL và Python."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_connection() -> bool:
    """Kiểm tra kết nối tới cơ sở dữ liệu."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1;"))
            dialect = engine.dialect.name.upper()
            print(f" [KẾT NỐI THÀNH CÔNG] Cơ sở dữ liệu: {dialect}")
            return True
    except Exception as exc:
        print(" [LỖI KẾT NỐI] Không thể kết nối tới cơ sở dữ liệu:", exc)
        return False


def init_db(schema_file: Optional[str] = None, drop_first: bool = False):
    """Khởi tạo toàn bộ bảng và chỉ mục theo schema SQL hoặc ORM."""
    project_root = Path(__file__).resolve().parent.parent
    if schema_file is None:
        schema_file = project_root / "sql" / "schema.sql"
    else:
        schema_file = Path(schema_file)

    if drop_first:
        print(" Đang xóa các bảng cũ để tái tạo schema mới (drop_first=True)...")
        tables_reverse_order = [
            "fact_interactions",
            "dim_product",
            "dim_category",
            "dim_user",
            "dim_time",
        ]
        with engine.connect() as conn:
            for tbl in tables_reverse_order:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE;"))
                except Exception:
                    pass
            conn.commit()

    if engine.dialect.name == "postgresql" and schema_file.exists():
        print(f" Đang đọc và thực thi DDL PostgreSQL từ file: {schema_file}...")
        with open(schema_file, "r", encoding="utf-8") as file:
            sql_script = file.read()

        with engine.connect() as connection:
            statements = [stmt.strip() for stmt in sql_script.split(";") if stmt.strip()]
            for statement in statements:
                connection.execute(text(statement))
            connection.commit()
        print(" Khởi tạo Star Schema và Indexes trên PostgreSQL thành công!")
    else:
        print(" Đang khởi tạo các bảng Data Warehouse thông qua SQLAlchemy ORM Base...")
        Base.metadata.create_all(bind=engine)
        print(" Khởi tạo ORM metadata thành công!")


def query_dataframe(sql: str, params: Optional[dict] = None) -> pd.DataFrame:
    """Thực thi câu truy vấn SQL và trả về kết quả dưới dạng Pandas DataFrame."""
    with engine.connect() as connection:
        return pd.read_sql_query(text(sql), connection, params=params)


if __name__ == "__main__":
    print(f"Đang kiểm tra kết nối tới {DATABASE_URL}...")
    is_connected = test_connection()
    if is_connected:
        init_db()
    else:
        print(" Lưu ý: Hãy bật Docker container PostgreSQL bằng lệnh:")
        print("   docker compose -f docker/docker-compose.yml up -d")
