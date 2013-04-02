Manwë
=====

A Python client library and command line interface to the `Varda
<https://github.com/martijnvermaat/varda>`_ database for genomic variation
frequencies.

**Warning:** This is a work in progress, probably not yet ready for use!


Description
-----------

Manwë is a Python client library for communicating with a Varda server. The
intent of Manwë is to offer the complete Varda API, but on an abstraction
level that is nice to work with from Python code. ::

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

::

    >>> for sample in session.samples(user=user):
    ...     print sample.name
    Sample 1
    My Second Sample
    Another Sample

Additionally, a simple command line client is built on top of the library that
can be used to run tasks from the command line, such as creating users and
importing samples. It is non-interactive and therefore suitable for use from
existing scripts and pipelines. Communication with Varda is done using the
`Requests <http://python-requests.org>`_ library. ::

    manwe import-sample 'Test' --vcf snps.vcf indels.vcf --bed coverage.bed


Running Manwë
-------------

Install the requirements listed in `requirements.txt`::

    $ pip install -r requirements.txt

You can now run the client directly like this::

    $ python -m manwe.commands -h

Or install Manwë to have it available globally::

    $ python setup.py install
    $ manwe -h


Documentation
-------------

Todo (surprise, surprise).


Copyright
---------

Manwë is licensed under the MIT License, see the LICENSE file for details. See
the AUTHORS file for a list of authors.