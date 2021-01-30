import setuptools
import io
import os

REQUIREMENTS = [
    "PyYAML",
    "python-crontab",
    "requests",
    "urllib3"
]


# Grab long description from README, this is shown on PyPi
with io.open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="SimplyPrintRPiSoftware",
    version="2.5.0",  # This MUST match the version in base.py
    author="SimplyPrint",
    author_email="albert@simplyprint.io",
    description="The SimplyPrint software used to communicate with the platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://simplyprint.io",  # TODO?
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 2.7",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: POSIX :: Linux",
    ],
    include_package_data=True,
    install_requires=REQUIREMENTS,
    # Python 2.7.9+, and Python 3.6+ - this matches OctoPrint 1.4.0.
    python_requires=">=2.7.9, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, !=3.5.*, <4",
)
