"""Run a source-separated snapshot experiment from a frozen config."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from value_of_wait.phase1_runner import main
if __name__ == "__main__":
    main()
