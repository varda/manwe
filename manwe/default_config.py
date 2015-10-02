# -*- coding: utf-8 -*-
"""
Manwë default configuration settings.
"""


#: Varda API root endpoint.
API_ROOT = 'http://127.0.0.1:5000'

#: Varda API authentication token.
TOKEN = None

#: Number of resources to query per collection request.
COLLECTION_CACHE_SIZE = 20

#: Size of chunks to yield from data iterator in bytes.
DATA_BUFFER_SIZE = 1024 * 1024

#: Whether or not to verify the API SSL certificate, or a path to a CA_BUNDLE
#: file with certificates of trusted CAs.
VERIFY_CERTIFICATE = True
