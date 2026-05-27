import sys
from pathlib import Path

# Add backend directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Add root directory (for config, core, etc.)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
