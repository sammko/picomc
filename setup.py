from setuptools import find_packages, setup

from distversion import make_version_cmdclass

PKG_NAME = "picomc"

version, cmdclass = make_version_cmdclass(PKG_NAME)

setup(
    name=PKG_NAME,
    version=version,
    cmdclass=cmdclass,
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
