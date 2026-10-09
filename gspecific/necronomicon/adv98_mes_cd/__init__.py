"""Necronomicon CD containers, translation JSON and full-workspace builds."""
from pathlib import Path
import sys

CORE_ROOT = Path(__file__).resolve().parents[3]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(1, str(CORE_ROOT))
