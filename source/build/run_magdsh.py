"""打包入口：让 PyInstaller 以包内相对导入方式启动 magdsh。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from magdsh.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
