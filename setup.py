import re

from setuptools import find_packages, setup

with open("picomc/__init__.py", encoding="utf8") as f:
    version = re.search(r'__version__ = "(.*?)"', f.read()).group(1)


setup(
    name="picomc",
    version=version,
    description="A very small CLI Minecraft launcher.",
    url="https://git.sammserver.com/sammko/picomc",
    author="Samuel Čavoj",
    author_email="samuel@cavoj.net",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    packages=find_packages(),
    install_requires=["click", "requests", "urllib3", "certifi", "tqdm", "coloredlogs"],
    python_requires=">=3",
    entry_points={"console_scripts": ["picomc = picomc:main"]},
)
