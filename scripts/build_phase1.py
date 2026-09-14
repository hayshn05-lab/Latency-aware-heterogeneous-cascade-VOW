"""Build phase-one experiment tables from the local cached database."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from value_of_wait.phase1_build import main
if __name__ == "__main__":
    main()
