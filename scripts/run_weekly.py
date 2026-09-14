"""Export a configured weekly Findata dataset or rebuild it offline."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from value_of_wait.weekly import main
if __name__=='__main__':raise SystemExit(main())
