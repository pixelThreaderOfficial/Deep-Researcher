import logging
import sys
from io import BytesIO
from pathlib import Path

import fitz
import pdfplumber
import requests

from docParsers.ollamaWorker import FastSummarizer
from sse.event_bus import event_bus
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler

BASE_DIR = Path(__file__).parent

# ====================== CLEAN LOGGER SETUP ======================
LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Suppress noisy libraries
logging.getLogger("fitz").setLevel(logging.WARNING)
logging.getLogger("pdfplumber").setLevel(logging.WARNING)
logging.getLogger("pymupdf").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("PDFParser")


def extract_pdf_to_md(pdf_path):
    """Extract text + tables from PDF. Supports local path and URL.
    Raises exception only on critical failures."""

    is_url = isinstance(pdf_path, str) and pdf_path.startswith(("http://", "https://"))

    # ---------- Download or Open File ----------
    if is_url:
        logger.info(f"Downloading PDF from URL: {pdf_path}")
        try:
            response = requests.get(pdf_path, timeout=60)
            response.raise_for_status()
            file_stream = BytesIO(response.content)
            logger.info("PDF download successful")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error downloading {pdf_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to download PDF from {pdf_path}: {e}")
            raise
    else:
        logger.info(f"Opening local PDF: {pdf_path}")
        file_stream = None

    try:
        # ---------- Text Extraction (fitz) ----------
        logger.info("Extracting text from PDF")
        if is_url:
            doc = fitz.open(stream=file_stream.getvalue(), filetype="pdf")
        else:
            doc = fitz.open(pdf_path)

        text_parts = [page.get_text("text") for page in doc]
        full_text = "\n".join(text_parts).strip()
        doc.close()

        # ---------- Tables Extraction (pdfplumber) ----------
        logger.info("Extracting tables from PDF")
        tables_md = []

        if is_url:
            file_stream.seek(0)
            with pdfplumber.open(file_stream) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables():
                        if not table or len(table) < 2:
                            continue
                        header = clean_row(table[0])
                        rows = [clean_row(r) for r in table[1:]]
                        md = "| " + " | ".join(header) + " |\n"
                        md += "| " + " | ".join(["---"] * len(header)) + " |\n"
                        for row in rows:
                            md += "| " + " | ".join(row) + " |\n"
                        tables_md.append(md)
        else:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables():
                        if not table or len(table) < 2:
                            continue
                        header = clean_row(table[0])
                        rows = [clean_row(r) for r in table[1:]]
                        md = "| " + " | ".join(header) + " |\n"
                        md += "| " + " | ".join(["---"] * len(header)) + " |\n"
                        for row in rows:
                            md += "| " + " | ".join(row) + " |\n"
                        tables_md.append(md)

        tables_text = "\n\n".join(tables_md)

        return f"# Extracted Content\n\n{full_text}\n\n# Tables\n\n{tables_text}"

    except Exception as e:
        logger.error(f"Failed to parse PDF {pdf_path}: {e}")
        raise
    finally:
        if is_url and "file_stream" in locals() and file_stream:
            file_stream.close()


def clean_row(row):
    return [str(cell).strip() if cell is not None else "" for cell in row]


async def extract_text_summarized(pdf_path, summarizer_url):
    try:
        text = extract_pdf_to_md(pdf_path)
        await scheduler.schedule(
            quickLog,
            params={
                "message": f"Extracted {pdf_path} now summarizing it!",
                "level": "success",
                "urgency": "none",
                "module": ["UTILS"],
            },
        )
        logger.info(f"Extracted PDF content, now summarizing: {pdf_path}")
        return FastSummarizer(base_url=summarizer_url).summarize(text)

    except Exception as e:
        logger.error(f"Failed to process {pdf_path} for summarization: {e}")
        return f"ERROR: Failed to extract or summarize {pdf_path}\n{str(e)}"


async def bulk_extract_text_summarized(pdf_paths, summarizer_url):
    results = {}
    await event_bus.broadcast(message={"msg": "Reading & Summarizing PDF Files!"})

    for pdf_path in pdf_paths:
        try:
            results[pdf_path] = await extract_text_summarized(pdf_path, summarizer_url)
        except Exception as e:
            logger.warning(f"Skipped {pdf_path} due to error: {e}")
            results[pdf_path] = f"ERROR: Could not process this file. {str(e)}"

    return results


# ====================== TEST ======================
# async def _test():
#     pdf_list = [
#         "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",  # Good
#         "https://www.orimi.com/pdf-test.pdf",  # Bad (403)
#         "https://arxiv.org/pdf/2601.00044",
#         # r"D:\Commercial\some_local_file.pdf"   # You can mix local paths too
#     ]

#     result = await bulk_extract_text_summarized(
#         pdf_list, "http://localhost:11434/api/generate"
#     )

#     print(result)

#     print("\n=== FINAL RESULT ===")
#     for path, content in result.items():
#         print(f"\n--- {path} ---")
#         print(content[:500] + "..." if len(str(content)) > 500 else content)  # Preview


# if __name__ == "__main__":
#     import asyncio

#     asyncio.run(_test())
