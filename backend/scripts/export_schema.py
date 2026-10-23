"""Exports MySQL DDL (database/schema.sql) and a Mermaid ER diagram (docs/ERD.md) from the ORM models."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import mysql
from app.database import Base
from app import models  # noqa

root = Path(__file__).resolve().parents[2]
d = mysql.dialect()
out = ["-- WorkForce AI Pro – MySQL 8 schema (generated from SQLAlchemy models)\n",
       "CREATE DATABASE IF NOT EXISTS workforce_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\nUSE workforce_ai;\nSET FOREIGN_KEY_CHECKS=0;\n"]
for t in Base.metadata.sorted_tables:
    out.append(str(CreateTable(t).compile(dialect=d)).strip() + " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n")
    for ix in sorted(t.indexes, key=lambda i: i.name or ""):
        out.append(str(CreateIndex(ix).compile(dialect=d)).strip() + ";")
    out.append("")
out.append("SET FOREIGN_KEY_CHECKS=1;")
(root / "database").mkdir(exist_ok=True)
(root / "database" / "schema.sql").write_text("\n".join(out))

er = ["# Entity-Relationship Diagram\n", "```mermaid", "erDiagram"]
for t in Base.metadata.sorted_tables:
    for fk in t.foreign_keys:
        er.append(f"    {fk.column.table.name} ||--o{{ {t.name} : \"{fk.parent.name}\"")
for t in Base.metadata.sorted_tables:
    er.append(f"    {t.name} {{")
    for c in t.columns:
        tag = " PK" if c.primary_key else (" FK" if c.foreign_keys else "")
        er.append(f"        {str(c.type).split('(')[0].replace(' ', '_')} {c.name}{tag}")
    er.append("    }")
er.append("```")
(root / "docs" / "ERD.md").write_text("\n".join(er))
print("tables:", len(Base.metadata.sorted_tables))
