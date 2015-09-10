Manwë
=====

**Warning:** This is a work in progress, probably not yet ready for use!

Manwë is a Python client library for working with the `Varda`_ database for
genomic variation frequencies. It also provides a command line interface to
some of its functionality.

The main goal of Manwë is to offer the complete Varda API, but on an
abstraction level that is nice to work with from Python code.

.. code-block:: pycon

    >>> import manwe
    >>> session = manwe.Session()
    >>> user = session.create_user('testlogin', 'password')
    >>> user.dirty
    False
    >>> user.name = 'Test User'
    >>> user.dirty
    True
    >>> user.save()
    >>> user.dirty
    False
    >>> for sample in session.samples():
    ...     print sample.user.name
    ...
    Rob Userman
    Barry Robsfriend
    Rob Userman

To install the latest release via PyPI using pip::

    pip install manwe


Documentation
-------------

The `latest documentation <http://manwe.readthedocs.org/>`_ with user guide
and API reference is hosted at Read The Docs.

You can also compile the documentation directly from the source code by
running ``make html`` from the ``doc/`` subdirectory. This requires `Sphinx`_
to be installed.


Copyright
---------

Manwë is licensed under the MIT License, see the LICENSE file for details. See
the AUTHORS file for a list of authors.


.. _Sphinx: http://sphinx-doc.org/
.. _Varda: https://github.com/varda/varda
