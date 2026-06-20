from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="openwrt-cli",
    version="1.0.0",
    author="",
    description="AI-Agent Ready OpenWrt CLI 管理工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ikuaidev/openwrt-cli",
    packages=find_packages(),
    py_modules=["main"],  # root-level main.py
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "paramiko>=3.0.0",
        "pyyaml>=6.0",
        "questionary>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "openwrt=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt"],
    },
)