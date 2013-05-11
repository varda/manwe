Installation
============

The Manwë source code is `hosted on GitHub
<https://github.com/martijnvermaat/manwe>`_. Supported Python versions for
running Manwë are 2.7 and PyPy (unit tests are run automatically on these
platforms `using the Travis CI service
<https://travis-ci.org/martijnvermaat/manwe>`_). Manwë can be installed either
via the Python Package Index (PyPI) or from the source code.


Latest release via PyPI
-----------------------

To install the latest release via PyPI using pip::

    pip install manwe


Development version
-------------------

You can also clone and use the latest development version directly from the
GitHub repository::

    git clone https://github.com/martijnvermaat/manwe.git
    cd manwe
    pip install -r requirements.txt
    python setup.py install
