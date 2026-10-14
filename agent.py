"""Compatibility entry point for backend.agent."""
import sys
from backend import agent as implementation

if __name__ == '__main__':
    implementation.main()
else:
    sys.modules[__name__] = implementation
