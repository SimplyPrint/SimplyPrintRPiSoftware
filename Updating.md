# How to deploy an update to SimplyPrintRPiSoftware

New update ready to be released? Build workflow below:

### Bump the version numbers

Version number needs to be increased in:
* `setup.py`
* `simplyprint_raspberry/base.py`

### Build the distribution

* `python setup.py sdist`

This will build the distribution under the `dist/` subfolder. Now might be a good time to 
`pip install SimplyPrintRPiSoftware-2.4.1.tar.gz` or whatever the file name is, and fully test it.

### Upload to TestPyPi

*Note:* You will need a TestPyPi account for this

Uploading to TestPyPi helps verify that everything is setup right for the update.

Once files are uploaded to PyPi or TestPyPi they cannot be changed.
To upload, you can use twine:

Install twine:
* `python -m pip install twine`
* `python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*`

Sign in with your username/password for TestPyPi, then it should give you a link to check
it has deployed properly.

### Upload to PyPi

Here we go! Considering all went well, it is just one command:

* `python -m twine upload dist/*`

### Deploy!

However you want to do this, using your update scripts, bump the version there
so it can be downloaded from PyPi.
