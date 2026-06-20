from setuptools import setup, find_packages
import sys
import os


def _prompt_config():
    """安装完成后提示用户运行配置向导"""
    print("")
    print("=" * 46)
    print("  openwrt-cli 安装成功！")
    print("=" * 46)
    print("")
    print("  首次使用需要配置路由器连接：")
    print("")
    print("    openwrt-cli config")
    print("")
    # 仅交互式终端自动引导
    if sys.stdin.isatty():
        try:
            import questionary
            from commands.config import run as config_run
            config_run()
        except Exception:
            pass


from setuptools.command.install import install as _InstallCommand


class InstallCommand(_InstallCommand):
    def run(self):
        super().run()
        _prompt_config()


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="openwrt-cli",
    version="1.0.0",
    author="",
    description="AI-Agent Ready OpenWrt CLI 管理工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/a6726170/openwrt-cli",
    packages=find_packages(),
    py_modules=["main"],
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
    cmdclass={"install": InstallCommand},
)
