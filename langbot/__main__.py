"""
LangBot CLI entry point for uvx/pip installations
"""

import os
import sys
import asyncio
import argparse


def main():
    """Main entry point for the langbot CLI command"""

    # Set up the package root directory as the working directory
    # When installed via pip/uvx, we need to locate the package installation
    import langbot
    package_dir = os.path.dirname(os.path.abspath(langbot.__file__))

    # Check if we're running from an installed package
    # In that case, we need to use the package's bundled files
    os.chdir(package_dir)

    # Import the original main entry
    from langbot.main import main_entry

    # Run the main entry point
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(main_entry(loop))
    except KeyboardInterrupt:
        print("\nLangBot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting LangBot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
