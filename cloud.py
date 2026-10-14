"""Compatibility import for backend.cloud."""
import sys
from backend import cloud as implementation

sys.modules[__name__] = implementation
