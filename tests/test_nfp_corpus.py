import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_nfp_corpus.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_nfp_corpus", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


nfp = _load_module()


def test_record_from_text_keeps_filename_as_source() -> None:
    record = nfp.record_from_text(
        filename="NFP Grading Scale.pdf",
        text="Distinction 80-100\n\nPass 40-49\n",
    )
    assert record is not None
    assert record["title"] == "NFP Grading Scale"
    assert record["url"] == "NFP Grading Scale.pdf"
    assert record["section"] == "NFP"
    assert "Distinction 80-100" in record["text"]
    assert "\n\n" not in record["text"]


def test_record_from_text_skips_empty_extract() -> None:
    assert nfp.record_from_text(filename="blank.pdf", text="  \n") is None
