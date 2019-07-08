from setuptools import find_packages, setup

from picomc import __version__

setup(
    name="picomc",
    version=__version__,
    description="A very small CLI Minecraft launcher.",
    url="https://git.sammserver.com/sammko/picomc",
    author="Samuel Čavoj",
    author_email="sammko@sammserver.com",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    packages=find_packages(),
    install_requires=["click", "requests", "urllib3", "certifi", "tqdm"],
    python_requires=">=3",
    entry_points={"console_scripts": ["picomc = picomc:main"]},
)
