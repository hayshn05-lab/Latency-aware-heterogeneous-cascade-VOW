"""Audit the configured SQLite dataset without network or model access."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from value_of_wait.weekly_audit import main
if __name__=='__main__':raise SystemExit(main())
