Manwë
=====

.. warning:: This is a work in progress, probably not yet ready for use!

Manwë is a Python client library for working with the `Varda`_ database for
genomic variation frequencies. It also provides a command line interface to
some of its functionality.

The main goal of Manwë is to offer the complete Varda API, but on an
abstraction level that is nice to work with from Python code.

::

    >>> import manwe
    >>> session = manwe.Session()
    >>> user = session.add_user('testlogin', 'password')
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


User documentation
------------------

New users should probably start here.

.. toctree::
   :maxdepth: 1

   install
   guide
   commands


API reference
-------------

Documentation on a specific function, class or method can be found in the API
reference.

.. toctree::
   :maxdepth: 2

   api


Additional notes
----------------

.. toctree::
   :maxdepth: 2

   development
   changelog
   copyright


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. _Varda: https://github.com/varda/varda
