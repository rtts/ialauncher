import os
import sys
import tomllib

from cx_Freeze import Executable, setup

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(root)
sys.path.insert(0, root)

with open("pyproject.toml", "rb") as f:
    project = tomllib.load(f)["project"]

with open("temp.py", "w") as f:
    f.write("""
from ialauncher.__main__ import main
if __name__ == '__main__':
    main()
""")

setup(
    name="IA Launcher",
    version=project["version"],
    description=project["description"],
    author=project["authors"][0]["name"],
    author_email=project["authors"][0]["email"],
    url=project["urls"]["Homepage"],
    options={
        "build_exe": {
            "packages": ["ialauncher", "games"],
            "include_msvcr": True,
        },
        "bdist_msi": {
            "product_name": "IA Launcher",
            "output_name": f"ialauncher-{project['version']}-win64.msi",
            "upgrade_code": "{5CFBACDE-7A56-4C59-879B-A5B263B5D68A}",
            "all_users": False,
            "install_icon": "windows/ia.ico",
            "directories": [("ProgramMenuFolder", "TARGETDIR", ".")],
        },
    },
    executables=[
        Executable(
            "temp.py",
            target_name="ialauncher.exe",
            base="gui",
            shortcut_name="IA Launcher",
            shortcut_dir="ProgramMenuFolder",
            icon="windows/ia.ico",
        )
    ],
)

os.remove("temp.py")
