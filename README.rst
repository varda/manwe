Manwë
=====

Manwë is a Python client library for working with the `Varda`_ database for
genomic variation frequencies. It also provides a command line interface to
some of its functionality.

**Warning:** This is a work in progress, probably not yet ready for use!

The main goal of Manwë is to offer the complete Varda API, but on an
abstraction level that is nice to work with from Python code.

.. code-block:: pycon

    >>> import manwe
    >>> session = manwe.Session()
    >>> user = add_user('testlogin', 'password')
    >>> user.uri
    '/users/1'
    >>> user.dirty
    False
    >>> user.name = 'Test User'
    >>> user.dirty
    True
    >>> user.save()
    >>> user.dirty
    False

.. code-block:: pycon

    >>> for sample in session.samples(user=user):
    ...     print sample.name
    ...
    Sample 1
    My Second Sample
    Another Sample

::

    $ manwe import-sample 'Test' --vcf snps.vcf indels.vcf --bed coverage.bed

To install the latest release via PyPI using pip::

    pip install manwe


Documentation
-------------

The latest documentation including a user guide and API reference is `hosted
at Read The Docs <http://manwe.readthedocs.org/>`_.

You can also compile the documentation directly from the source code by
running ``make html`` from the ``doc/`` subdirectory. This requires `Sphinx`_
to be installed.


Copyright
---------

Manwë is licensed under the MIT License, see the ``LICENSE`` file for
details. See the ``AUTHORS`` file for a list of authors.


.. _Sphinx: http://sphinx-doc.org/
.. _Varda: https://github.com/martijnvermaat/varda
