"""
conftest.py — Shared test configuration.

Ensures src/ is on sys.path so all test modules can import from src/.
"""
import sys
import os

# Add src/ to Python path for all tests
src_path = os.path.join(os.path.dirname(__file__), "..", "src")
if src_path not in sys.path:
    sys.path.insert(0, os.path.abspath(src_path))
