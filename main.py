import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.bot import run_bot

if __name__ == "__main__":
    run_bot()
