from setuptools import setup, find_packages

setup(
    name="agy-account-switch",
    version="0.2.0",
    description="Multi-account switcher with OpenSSL AES-256-CBC encryption for Google Antigravity CLI",
    author="tekotechkotech",
    packages=find_packages(),
    py_modules=["account_switch", "agy_account_cli", "encryption"],
    python_requires=">=3.8",
    install_requires=[
        "keyring>=23.0.0",
    ],
    extras_require={
        "test": [
            "pytest>=7.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "agy-account=agy_account_switch.agy_account_cli:main",
        ],
    },
)
