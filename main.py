#!/usr/bin/env python3
"""
Zyxel EX5601-T0 / MT7986 OpenWrt Bootloader Unlocker & Flasher
GUI & CLI Launcher
"""
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and not (len(sys.argv) == 2 and sys.argv[1] == "--gui"):
        from zyxel_flasher.cli import run_cli
        run_cli()
    else:
        from zyxel_flasher.gui import ZyxelFlasherGUI
        app = ZyxelFlasherGUI()
        app.mainloop()
