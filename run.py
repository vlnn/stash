import os
import sys

from stash.cli import main

if __name__ == "__main__":
    main(sys.argv[1:], os.environ)
