from setuptools import setup, find_packages

setup(
    name="anime-character-loader",
    version="2.4.0",
    description="Generate validated anime character SOUL.md for OpenClaw agents",
    author="colinchen4",
    url="https://github.com/colinchen4/anime-character-loader",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "anime-character-loader=anime_character_loader.cli:main",
        ],
    },
    python_requires=">=3.9",
)