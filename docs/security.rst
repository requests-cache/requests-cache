.. _security:

Security
========

Pickle Vulnerabilities
----------------------
.. warning:: The python ``pickle`` module has `known security vulnerabilities <https://docs.python.org/3/library/pickle.html>`_,
    potentially leading to code execution when deserialzing data.

This means it should only be used to deserialize data that you trust hasn't been tampered with.
Since this isn't always possible, requests-cache can optionally use
`itsdangerous <https://itsdangerous.palletsprojects.com>`_ to add a layer of security around these operations.
It works by signing serialized data with a secret key that you control. Then, if the data is tampered
with, the signature check fails and raises an error.

Creating and Storing a Secret Key
---------------------------------
To enable this behavior, first create a secret key, which can be any ``str`` or ``bytes`` object.

One common pattern for handling this is to store it wherever you store the rest of your credentials
(`Linux keyring <https://itsfoss.com/ubuntu-keyring>`_,
`macOS keychain <https://support.apple.com/guide/mac-help/use-keychains-to-store-passwords-mchlf375f392/mac>`_,
`password database <https://keepassxc.org>`_, etc.),
set it in an environment variable, and then read it in your application:

    >>> import os
    >>> secret_key = os.environ['SECRET_KEY']

Alternatively, you can use the `keyring <https://keyring.readthedocs.io>`_ package to read the key
directly:

    >>> import keyring
    >>> secret_key = keyring.get_password('requests-cache-example', 'secret_key')

Signing Cached Responses
------------------------
Once you have your key, just pass it to :py:class:`.CachedSession` or :py:func:`.install_cache` to start using it:

    >>> from requests_cache import CachedSession
    >>> session = CachedSession(secret_key=secret_key)
    >>> session.get('https://httpbin.org/get')

You can verify that it's working by modifying the cached item (*without* your key):

    >>> session_2 = CachedSession(secret_key='a different key')
    >>> cache_key = list(session_2.cache.responses.keys())[0]
    >>> session_2.cache.responses[cache_key] = 'exploit!'

Then, if you try to get that cached response again (*with* your key), you will get an error:

    >>> session.get('https://httpbin.org/get')
    BadSignature: Signature b'iFNmzdUOSw5vqrR9Cb_wfI1EoZ8' does not match
