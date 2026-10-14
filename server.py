"""Compatibility entry point for backend.server."""
import sys
from backend import server as implementation

if __name__ == '__main__':
    implementation.main()
else:
    sys.modules[__name__] = implementation
