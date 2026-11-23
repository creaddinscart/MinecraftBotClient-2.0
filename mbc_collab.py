#!/usr/bin/env python3
# MBC-2.0 standalone operator joiner entry point.
# Author: CREADDINSCART STUDIO + Mater Work + Loder Hankex + jake + jenmnmer + yig
# Made with CREADDINSCART STUDIO - https://www.shit.pub/studio/
#
# Bundled by build.py into `mbc-collab` (one file per platform) so an operator
# can join a running MBC-2.0 shared console WITHOUT having Python or the source.
#
#   mbc-collab --host <IP> --port 25599 --name Alice --token <secret>

import sys
import os

# When frozen, the src package is bundled inside; make it importable.
if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)

from src.ui.collab_client import main

if __name__ == "__main__":
    sys.exit(main())
