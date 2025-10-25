import os
import re
import json
import time
import hashlib
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import pypandoc
import pandas as pd

from markdown_pdf import MarkdownPdf, Section

# Basic Variables
DATABASE_URL = "exporter.sqlite3"
OUTPUT_DIR = "D:\\Commercial\\pixelThreader\\DeepResearcher\\app\\deep-researcher-v0-fb\\deep-researcher-backend-beta\\bucket\\_generated\\docs"
SALT_SECRET = os.getenv(
    "EXPORTER_SALT_SECRET",
    hashlib.sha256(f"{os.getpid()}-{time.time_ns()}-{os.urandom(16).hex()}".encode()).hexdigest(),
)

# --------------------------------------
# Utilities
# --------------------------------------

def ensure_output_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def slugify(value: str) -> str:
    if not value:
        return "export"
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\-_. ]+", "-", value)
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "export"


def compute_sha256(file_path: str) -> Optional[str]:
    try:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception:
        return None


def build_output_path(base_name: str, ext: str) -> str:
    ensure_output_dir()
    safe = slugify(base_name)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    rand = os.urandom(3).hex()  # 6 hex chars, reduces collision within same second
    filename = f"{safe}-{ts}-{rand}.{ext}"
    return os.path.join(OUTPUT_DIR, filename)


def normalize_output_path(preferred_output_path: Optional[str], ext: str, base_name: str) -> str:
    """
    Ensure the output path is under OUTPUT_DIR. If preferred path is provided and outside OUTPUT_DIR,
    rebase it into OUTPUT_DIR preserving the basename. If not provided, create one using base_name and timestamp.
    """
    ensure_output_dir()
    if not preferred_output_path or not preferred_output_path.strip():
        return build_output_path(base_name, ext)

    abs_out = os.path.abspath(preferred_output_path)
    # Ensure extension
    if not abs_out.lower().endswith(f".{ext}"):
        abs_out = f"{abs_out}.{ext}"

    output_root = os.path.abspath(OUTPUT_DIR)
    # Normalize to OUTPUT_DIR if outside
    if not abs_out.lower().startswith(output_root.lower() + os.sep):
        abs_out = os.path.join(output_root, os.path.basename(abs_out))

    os.makedirs(os.path.dirname(abs_out), exist_ok=True)
    return abs_out


# --------------------------------------
# SQLite helpers
# --------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exports (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('started','success','failure')),
              success INTEGER NOT NULL CHECK(success IN (0,1)),
              format TEXT NOT NULL,
              source_type TEXT CHECK(source_type IN ('file','text')),
              input_path TEXT,
              output_path TEXT NOT NULL,
              message TEXT,
              error TEXT,
              bytes_size INTEGER,
              rows INTEGER,
              columns INTEGER,
              duration_ms INTEGER,
              checksum_sha256 TEXT,
              unique_hash TEXT,
              metadata_json TEXT
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exports_created_at ON exports(created_at);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exports_format ON exports(format);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exports_status ON exports(status);")

        # Ensure unique_hash exists if table created previously without it
        cols = {r[1] for r in conn.execute("PRAGMA table_info(exports)").fetchall()}
        if "unique_hash" not in cols:
            conn.execute("ALTER TABLE exports ADD COLUMN unique_hash TEXT;")


def db_start_export(fmt: str, source_type: str, input_path: Optional[str], output_path: str) -> int:
    init_db()
    now = utc_now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO exports (created_at, updated_at, status, success, format, source_type, input_path, output_path)
            VALUES (?, ?, 'started', 0, ?, ?, ?, ?)
            """,
            (now, now, fmt, source_type, input_path, output_path),
        )
        return int(cur.lastrowid)


def _get_created_at(export_id: int) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute("SELECT created_at FROM exports WHERE id=?", (export_id,)).fetchone()
        return row["created_at"] if row else None


def compute_unique_hash(
    base_checksum: Optional[str],
    output_path: Optional[str],
    export_id: int,
    created_at_iso: Optional[str],
    nonce: Optional[str] = None,
) -> str:
    """
    Produce a per-export salted unique hash. Even for identical files/paths, the nonce ensures uniqueness.
    Includes SALT_SECRET, export_id, created_at, output_path, base checksum and a random nonce.
    """
    if nonce is None:
        nonce = os.urandom(16).hex()
    parts = [
        "v1",
        SALT_SECRET,
        str(export_id),
        created_at_iso or "",
        output_path or "",
        base_checksum or "",
        nonce,
    ]
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return h


def db_finish_success(
    export_id: int,
    output_path: str,
    message: str,
    rows: Optional[int] = None,
    columns: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    now = utc_now_iso()
    bytes_size = os.path.getsize(output_path) if os.path.exists(output_path) else None
    checksum = compute_sha256(output_path) if os.path.exists(output_path) else None
    created_at = _get_created_at(export_id)
    duration_ms = None
    if created_at:
        try:
            started = datetime.fromisoformat(created_at.replace("Z", ""))
            duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        except Exception:
            duration_ms = None
    # salted unique hash to guarantee uniqueness per export
    unique_h = compute_unique_hash(checksum, output_path, export_id, created_at)
    with _connect() as conn:
        conn.execute(
            """
            UPDATE exports
            SET updated_at=?, status='success', success=1, message=?, bytes_size=?, rows=?, columns=?, duration_ms=?, checksum_sha256=?, unique_hash=?, metadata_json=?
            WHERE id=?
            """,
            (
                now,
                message,
                bytes_size,
                rows,
                columns,
                duration_ms,
                checksum,
                unique_h,
                json.dumps(metadata) if metadata else None,
                export_id,
            ),
        )


def db_finish_failure(
    export_id: int,
    output_path: Optional[str],
    message: str,
    error: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    now = utc_now_iso()
    created_at = _get_created_at(export_id)
    duration_ms = None
    if created_at:
        try:
            started = datetime.fromisoformat(created_at.replace("Z", ""))
            duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        except Exception:
            duration_ms = None
    with _connect() as conn:
        conn.execute(
            """
            UPDATE exports
            SET updated_at=?, status='failure', success=0, message=?, error=?, duration_ms=?, metadata_json=?
            WHERE id=?
            """,
            (
                now,
                message,
                error,
                duration_ms,
                json.dumps(metadata) if metadata else None,
                export_id,
            ),
        )


def get_export(export_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM exports WHERE id=?", (export_id,)).fetchone()
        return dict(row) if row else None


def list_exports(fmt: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM exports"
    clauses = []
    params: List[Any] = []
    if fmt:
        clauses.append("format=?")
        params.append(fmt)
    if status:
        clauses.append("status=?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]


# --------------------------------------
# Base exporter mixin
# --------------------------------------

class BaseExporter:
    def _resolve_out(self, preferred_output_path: Optional[str], ext: str, base_name: str) -> str:
        return normalize_output_path(preferred_output_path, ext, base_name)

    def _start(self, fmt: str, source_type: str, input_path: Optional[str], output_path: str) -> int:
        return db_start_export(fmt, source_type, input_path, output_path)

    def _success(self, export_id: int, output_path: str, message: str, rows: Optional[int] = None, columns: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        db_finish_success(export_id, output_path, message, rows, columns, metadata)
        result: Dict[str, Any] = {
            "success": True,
            "status": "success",
            "export_id": export_id,
            "message": message,
            "output_file": output_path,
        }
        # Enrich with computed fields from DB
        exp = get_export(export_id)
        if exp:
            for k in ("bytes_size", "rows", "columns", "duration_ms", "checksum_sha256"):
                if exp.get(k) is not None:
                    result[k] = exp[k]
        return result

    def _failure(self, export_id: int, output_path: Optional[str], message: str, error: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        db_finish_failure(export_id, output_path, message, error, metadata)
        return {
            "success": False,
            "status": "failure",
            "export_id": export_id,
            "message": message,
            "error": error,
            "output_file": output_path,
        }

class PDFExporter(BaseExporter):
    def __init__(self, input_encoding: str = 'utf-8'):
        """
        Initialize the PDF exporter
        
        Args:
            input_encoding (str): Encoding to use when reading markdown files. Defaults to utf-8.
        """
        self.input_encoding = input_encoding

    def read_markdown_file(self, file_path: str) -> Dict[str, Any]:
        """
        Safely read a markdown file with proper encoding handling
        
        Args:
            file_path (str): Path to the markdown file
            
        Returns:
            Dict[str, Any]: Response containing success status, message and content if successful
        """
        try:
            # First try with specified encoding
            with open(file_path, 'r', encoding=self.input_encoding) as f:
                return {
                    "success": True,
                    "message": "File read successfully",
                    "content": f.read()
                }
        except UnicodeDecodeError:
            # If that fails, try with utf-8-sig (handles BOM)
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    return {
                        "success": True,
                        "message": "File read successfully using utf-8-sig encoding",
                        "content": f.read()
                    }
            except UnicodeDecodeError:
                # Last resort: try with errors='replace' to handle unknown characters
                try:
                    with open(file_path, 'r', encoding=self.input_encoding, errors='replace') as f:
                        return {
                            "success": True,
                            "message": "File read with some character replacements",
                            "content": f.read()
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"Failed to read file: {str(e)}",
                        "error": str(e)
                    }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error reading file: {str(e)}",
                "error": str(e)
            }

    def convert_to_pdf(self, input_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert a markdown file to PDF with proper error handling
        
        Args:
            input_path (str): Path to the input markdown file
            output_path (Optional[str]): Path for the output PDF file. If None, will use same name as input with .pdf extension
            
        Returns:
            Dict[str, Any]: Response containing success status, message and additional info
        """
        try:
            # Validate input path
            input_path = os.path.abspath(input_path)
            if not os.path.exists(input_path):
                return {
                    "success": False,
                    "message": f"Input file does not exist: {input_path}",
                    "error": "FileNotFoundError"
                }

            # Resolve output path under OUTPUT_DIR
            output_path = self._resolve_out(output_path, "pdf", Path(input_path).stem)

            # Start DB record
            export_id = self._start("pdf", "file", input_path, output_path)

            # Read the markdown content
            read_result = self.read_markdown_file(input_path)
            if not read_result["success"]:
                return self._failure(export_id, output_path, read_result.get("message", "Failed to read input"), str(read_result.get("error")))

            # Convert to PDF
            pdf = MarkdownPdf()
            pdf.add_section(Section(read_result["content"]))
            pdf.save(output_path)

            ok = self._success(export_id, output_path, "PDF generated successfully")
            ok["input_file"] = input_path
            return ok

        except Exception as e:
            exp_id = None
            try:
                # If export_id was created
                exp_id = locals().get("export_id")
                out_p = locals().get("output_path") if "output_path" in locals() else None
                if exp_id is not None:
                    return self._failure(exp_id, out_p, "Error converting markdown to PDF", str(e))
            except Exception:
                pass
            return {"success": False, "message": f"Error converting markdown to PDF: {str(e)}", "error": str(e), "input_file": input_path, "output_file": locals().get("output_path") if "output_path" in locals() else None}


class DocxExporter(BaseExporter):
    def __init__(self):
        """
        Initialize the DOCX exporter
        """
        pass

    def convert_to_docx(self, markdown_text: str, output_file: str) -> Dict[str, Any]:
        """
        Convert markdown text to DOCX file

        Args:
            markdown_text (str): The markdown content to convert
            output_file (str): Path for the output DOCX file

        Returns:
            Dict[str, Any]: Response containing success status and message
        """
        try:
            # Validate inputs
            if not markdown_text or not markdown_text.strip():
                return {
                    "success": False,
                    "message": "Markdown text is empty or None",
                    "error": "EmptyInputError"
                }

            if not output_file or not output_file.strip():
                return {
                    "success": False,
                    "message": "Output file path is empty or None",
                    "error": "EmptyOutputPathError"
                }

            # Resolve output path under OUTPUT_DIR
            output_file = self._resolve_out(output_file, "docx", "export-docx")

            export_id = self._start("docx", "text", None, output_file)

            # Convert to DOCX
            pypandoc.convert_text(
                markdown_text,
                "docx",
                format="md",
                outputfile=output_file,
                extra_args=["--standalone"]
            )

            return self._success(export_id, output_file, f"Successfully converted to {output_file}")

        except Exception as e:
            exp_id = locals().get("export_id")
            out_p = locals().get("output_file") if "output_file" in locals() else None
            if exp_id is not None:
                return self._failure(exp_id, out_p, "Error converting markdown to DOCX", str(e))
            return {"success": False, "message": f"Error converting markdown to DOCX: {str(e)}", "error": str(e), "output_file": out_p}

    def convert_markdown_file_to_docx(self, input_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert a markdown file to DOCX with proper error handling

        Args:
            input_path (str): Path to the input markdown file
            output_path (Optional[str]): Path for the output DOCX file. If None, will use same name as input with .docx extension

        Returns:
            Dict[str, Any]: Response containing success status, message and additional info
        """
        try:
            # Validate input path
            input_path = os.path.abspath(input_path)
            if not os.path.exists(input_path):
                return {
                    "success": False,
                    "message": f"Input file does not exist: {input_path}",
                    "error": "FileNotFoundError"
                }

            # Resolve output path under OUTPUT_DIR
            output_path = self._resolve_out(output_path, "docx", Path(input_path).stem)

            export_id = self._start("docx", "file", input_path, output_path)

            # Read the markdown content
            read_result = PDFExporter().read_markdown_file(input_path)  # Reuse the reading logic
            if not read_result["success"]:
                return self._failure(export_id, output_path, read_result.get("message", "Failed to read input"), str(read_result.get("error")))

            # Convert to DOCX
            try:
                pypandoc.convert_text(read_result["content"], "docx", format="md", outputfile=output_path, extra_args=["--standalone"])
                ok = self._success(export_id, output_path, f"DOCX generated successfully from {input_path}")
                ok["input_file"] = input_path
                return ok
            except Exception as e:
                return self._failure(export_id, output_path, "Error converting markdown file to DOCX", str(e))

        except Exception as e:
            return {
                "success": False,
                "message": f"Error converting markdown file to DOCX: {str(e)}",
                "error": str(e),
                "input_file": input_path,
                "output_file": output_path if 'output_path' in locals() else None
            }


class XlsxExporter(BaseExporter):
    def __init__(self):
        """
        Initialize the XLSX exporter
        """
        pass

    def convert_to_xlsx(self, markdown_text: str, output_file: str) -> Dict[str, Any]:
        """
        Convert markdown text to XLSX file via CSV intermediate format

        Args:
            markdown_text (str): The markdown content to convert (should contain tables)
            output_file (str): Path for the output XLSX file

        Returns:
            Dict[str, Any]: Response containing success status and message
        """
        csv_path = None
        try:
            # Validate inputs
            if not markdown_text or not markdown_text.strip():
                return {
                    "success": False,
                    "message": "Markdown text is empty or None",
                    "error": "EmptyInputError"
                }

            if not output_file or not output_file.strip():
                return {
                    "success": False,
                    "message": "Output file path is empty or None",
                    "error": "EmptyOutputPathError"
                }

            # Resolve output path under OUTPUT_DIR
            output_file = self._resolve_out(output_file, "xlsx", "export-xlsx")

            export_id = self._start("xlsx", "text", None, output_file)

            # Create a temporary CSV file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_csv:
                csv_path = tmp_csv.name

            # Convert Markdown → CSV using Pandoc
            pypandoc.convert_text(
                markdown_text,
                "csv",
                format="md",
                outputfile=csv_path,
                extra_args=["--standalone"]
            )

            # Load CSV → DataFrame → Excel
            df = pd.read_csv(csv_path)
            df.to_excel(output_file, index=False)

            # Clean up temporary file
            os.remove(csv_path)

            return self._success(export_id, output_file, f"Successfully converted markdown table to {output_file}", rows=len(df), columns=len(df.columns))

        except Exception as e:
            # Clean up temporary file if it exists
            if csv_path and os.path.exists(csv_path):
                try:
                    os.remove(csv_path)
                except:
                    pass  # Ignore cleanup errors
            exp_id = locals().get("export_id")
            out_p = locals().get("output_file") if "output_file" in locals() else None
            if exp_id is not None:
                return self._failure(exp_id, out_p, "Error converting markdown to XLSX", str(e))
            return {"success": False, "message": f"Error converting markdown to XLSX: {str(e)}", "error": str(e), "output_file": out_p}

    def convert_markdown_file_to_xlsx(self, input_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert a markdown file to XLSX with proper error handling

        Args:
            input_path (str): Path to the input markdown file
            output_path (Optional[str]): Path for the output XLSX file. If None, will use same name as input with .xlsx extension

        Returns:
            Dict[str, Any]: Response containing success status, message and additional info
        """
        try:
            # Validate input path
            input_path = os.path.abspath(input_path)
            if not os.path.exists(input_path):
                return {
                    "success": False,
                    "message": f"Input file does not exist: {input_path}",
                    "error": "FileNotFoundError"
                }

            # Resolve output path under OUTPUT_DIR
            output_path = self._resolve_out(output_path, "xlsx", Path(input_path).stem)

            export_id = self._start("xlsx", "file", input_path, output_path)

            # Read the markdown content
            read_result = PDFExporter().read_markdown_file(input_path)  # Reuse the reading logic
            if not read_result["success"]:
                return self._failure(export_id, output_path, read_result.get("message", "Failed to read input"), str(read_result.get("error")))

            # Convert to XLSX
            try:
                # Create a temporary CSV file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_csv:
                    csv_path = tmp_csv.name
                pypandoc.convert_text(read_result["content"], "csv", format="md", outputfile=csv_path, extra_args=["--standalone"])
                df = pd.read_csv(csv_path)
                df.to_excel(output_path, index=False)
                try:
                    os.remove(csv_path)
                except Exception:
                    pass
                ok = self._success(export_id, output_path, f"XLSX generated successfully from {input_path}", rows=len(df), columns=len(df.columns))
                ok["input_file"] = input_path
                return ok
            except Exception as e:
                return self._failure(export_id, output_path, "Error converting markdown file to XLSX", str(e))

        except Exception as e:
            return {
                "success": False,
                "message": f"Error converting markdown file to XLSX: {str(e)}",
                "error": str(e),
                "input_file": input_path,
                "output_file": output_path if 'output_path' in locals() else None
            }


class CsvExporter(BaseExporter):
    def __init__(self):
        """
        Initialize the CSV exporter
        """
        pass

    def convert_to_csv(self, markdown_text: str, output_file: str) -> Dict[str, Any]:
        """
        Convert markdown table text to CSV file

        Args:
            markdown_text (str): The markdown content to convert (should contain tables)
            output_file (str): Path for the output CSV file

        Returns:
            Dict[str, Any]: Response containing success status and message
        """
        try:
            # Validate inputs
            if not markdown_text or not markdown_text.strip():
                return {
                    "success": False,
                    "message": "Markdown text is empty or None",
                    "error": "EmptyInputError"
                }

            if not output_file or not output_file.strip():
                return {
                    "success": False,
                    "message": "Output file path is empty or None",
                    "error": "EmptyOutputPathError"
                }

            # Resolve output path under OUTPUT_DIR
            output_file = self._resolve_out(output_file, "csv", "export-csv")

            export_id = self._start("csv", "text", None, output_file)

            # Convert Markdown → CSV using Pandoc
            pypandoc.convert_text(
                markdown_text,
                "csv",
                format="md",
                outputfile=output_file,
                extra_args=["--standalone"]
            )

            # Count rows and columns if file was created
            row_count = 0
            col_count = 0
            if os.path.exists(output_file):
                try:
                    df = pd.read_csv(output_file)
                    row_count = len(df)
                    col_count = len(df.columns)
                except Exception:
                    # If pandas can't read it, count lines manually
                    with open(output_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        row_count = len(lines) - 1 if lines else 0  # Subtract header
                        if lines:
                            col_count = len(lines[0].strip().split(',')) if lines[0].strip() else 0

            ok = self._success(
                export_id,
                output_file,
                f"Successfully converted markdown table to {output_file}",
                rows=row_count,
                columns=col_count,
            )
            return ok

        except Exception as e:
            exp_id = locals().get("export_id")
            out_p = locals().get("output_file") if "output_file" in locals() else None
            if exp_id is not None:
                return self._failure(exp_id, out_p, "Error converting markdown to CSV", str(e))
            return {"success": False, "message": f"Error converting markdown to CSV: {str(e)}", "error": str(e), "output_file": out_p}

    def convert_markdown_file_to_csv(self, input_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert a markdown file to CSV with proper error handling

        Args:
            input_path (str): Path to the input markdown file
            output_path (Optional[str]): Path for the output CSV file. If None, will use same name as input with .csv extension

        Returns:
            Dict[str, Any]: Response containing success status, message and additional info
        """
        try:
            # Validate input path
            input_path = os.path.abspath(input_path)
            if not os.path.exists(input_path):
                return {
                    "success": False,
                    "message": f"Input file does not exist: {input_path}",
                    "error": "FileNotFoundError"
                }

            # Resolve output path under OUTPUT_DIR
            output_path = self._resolve_out(output_path, "csv", Path(input_path).stem)

            export_id = self._start("csv", "file", input_path, output_path)

            # Read the markdown content
            read_result = PDFExporter().read_markdown_file(input_path)  # Reuse the reading logic
            if not read_result["success"]:
                return self._failure(export_id, output_path, read_result.get("message", "Failed to read input"), str(read_result.get("error")))

            # Convert to CSV
            try:
                pypandoc.convert_text(read_result["content"], "csv", format="md", outputfile=output_path, extra_args=["--standalone"])
                # Count rows/columns
                row_count = 0
                col_count = 0
                if os.path.exists(output_path):
                    try:
                        df = pd.read_csv(output_path)
                        row_count = len(df)
                        col_count = len(df.columns)
                    except Exception:
                        with open(output_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            row_count = len(lines) - 1 if lines else 0
                            if lines:
                                col_count = len(lines[0].strip().split(',')) if lines[0].strip() else 0
                ok = self._success(export_id, output_path, f"CSV generated successfully from {input_path}", rows=row_count, columns=col_count)
                ok["input_file"] = input_path
                return ok
            except Exception as e:
                return self._failure(export_id, output_path, "Error converting markdown file to CSV", str(e))

        except Exception as e:
            return {
                "success": False,
                "message": f"Error converting markdown file to CSV: {str(e)}",
                "error": str(e),
                "input_file": input_path,
                "output_file": output_path if 'output_path' in locals() else None
            }

# Example usage
if __name__ == "__main__":
    # PDF export example
    pdf_exporter = PDFExporter()
    input_file = "D:\\Commercial\\pixelThreader\\DeepResearcher\\app\\deep-researcher-v0-fb\\deep-researcher-backend-beta\\crawl4ai_custom_context.md"

    # Convert to PDF
    pdf_result = pdf_exporter.convert_to_pdf(input_file)
    print("PDF Export Result:", pdf_result)

    # Convert to DOCX
    docx_exporter = DocxExporter()
    docx_result = docx_exporter.convert_markdown_file_to_docx(input_file)
    print("DOCX Export Result:", docx_result)

    # Convert to XLSX
    xlsx_exporter = XlsxExporter()
    xlsx_result = xlsx_exporter.convert_markdown_file_to_xlsx(input_file)
    print("XLSX Export Result:", xlsx_result)

    # Convert to CSV
    csv_exporter = CsvExporter()
    csv_result = csv_exporter.convert_markdown_file_to_csv(input_file)
    print("CSV Export Result:", csv_result)

    # Direct conversions from text
    # DOCX example
    markdown_text = "# Hello World\n\nThis is a test document."
    docx_result2 = docx_exporter.convert_to_docx(markdown_text, "test_output.docx")
    print("Direct DOCX Export Result:", docx_result2)

    # XLSX and CSV examples with table data
    table_markdown = """
# Sales Report

| Product | Price | Units |
|----------|--------|--------|
| Laptop 💻 | 1200 | 5 |
| Mouse 🖱️ | 25 | 15 |
| Keyboard ⌨️ | 45 | 10 |
"""
    xlsx_result2 = xlsx_exporter.convert_to_xlsx(table_markdown, "test_sales.xlsx")
    print("Direct XLSX Export Result:", xlsx_result2)

    csv_result2 = csv_exporter.convert_to_csv(table_markdown, "test_sales.csv")
    print("Direct CSV Export Result:", csv_result2)