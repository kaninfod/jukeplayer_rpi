#!/usr/bin/env python3
"""
Jukeplayer Pi Client
Entry point for Raspberry Pi hardware client
"""

import sys
import asyncio
from app.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
