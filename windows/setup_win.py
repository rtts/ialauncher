import os
import sys
import tomllib

from cx_Freeze import Executable, setup

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(root)
sys.path.insert(0, root)

with open("pyproject.toml", "rb") as f:
    project = tomllib.load(f)["project"]

setup(
    name="IA Launcher",
    version=project["version"],
    description=project["description"],
    author="Return to the Source",
    author_email=project["authors"][0]["email"],
    url=project["urls"]["Homepage"],
    options={
        "build_exe": {
            "packages": ["ialauncher", "games"],
            "include_msvcr": True,
        },
        "bdist_msi": {
            "product_name": "IA Launcher",
            "output_name": f"ialauncher-{project['version']}-amd64.msi",
            "upgrade_code": "{5CFBACDE-7A56-4C59-879B-A5B263B5D68A}",
            "all_users": False,
            "install_icon": "windows/ia.ico",
            "directories": [
                ("ProgramMenuFolder", "TARGETDIR", "."),
                ("DesktopFolder", "TARGETDIR", "."),
            ],
            "data": {
                "Shortcut": [
                    (
                        "S_DESKTOP",
                        "DesktopFolder",
                        "IA Launcher",
                        "TARGETDIR",
                        "[TARGETDIR]ialauncher.exe",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "TARGETDIR",
                    )
                ],
            },
        },
    },
    executables=[
        Executable(
            "windows/main.py",
            target_name="ialauncher.exe",
            base="gui",
            shortcut_name="IA Launcher",
            shortcut_dir="ProgramMenuFolder",
            icon="windows/ia.ico",
        )
    ],
)
