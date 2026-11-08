"""Killable PDF parsing and OCR workers for untrusted showcase uploads."""
import asyncio
import json
import os
import signal
import sys
from pathlib import Path


async def run_document_worker(mode, *, path=None, content=None):
    from app import config

    process = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__).resolve()), mode, str(path or ""),
        start_new_session=True,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(
            process.communicate(content), config.get_settings().showcase_extraction_timeout_seconds
        )
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        await process.wait()
        raise
    if process.returncode:
        raise ValueError("Document could not be processed")
    return json.loads(stdout)


def _worker():
    # Load only the extractor, avoiding application initialization in the child.
    import importlib.util
    import io

    mode = sys.argv[1]
    if mode == "pages":
        import pdfplumber
        with pdfplumber.open(io.BytesIO(sys.stdin.buffer.read())) as pdf:
            return len(pdf.pages)
    filename = "pdf_extractor.py" if mode == "pdf" else "ocr_extractor.py"
    spec = importlib.util.spec_from_file_location("extractor", Path(__file__).parent / "extractors" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._extract_sync(Path(sys.argv[2]))


if __name__ == "__main__":
    print(json.dumps(_worker()))
