import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = ""
# Keep prompt edits from the developer machine out of the test process.
os.environ["UNMC_RAG_EXPERIMENT_PROMPT_OVERRIDES_PATH"] = str(
    Path(tempfile.mkdtemp(prefix="unmc-prompts-")) / "prompt_overrides.json"
)
