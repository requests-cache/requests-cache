Examples
--------
This section contains some complete examples that demonstrate the main features of requests-cache.

These can also be found in the
`examples/ <https://github.com/reclosedev/requests-cache/tree/master/examples>`_ folder on GitHub.


Basic usage (with sessions)
~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. include:: ../examples/log_requests.py
    :start-line: 2
    :end-line: 3

.. admonition:: Example code
    :class: toggle

    .. literalinclude:: ../examples/basic_usage.py
        :lines: 1,6-


Basic usage (with patching)
~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. include:: ../examples/session_patch.py
    :start-line: 3
    :end-line: 4

.. admonition:: Example code
    :class: toggle

    .. literalinclude:: ../examples/session_patch.py
        :lines: 1,6-


Cache expiration
~~~~~~~~~~~~~~~~
.. include:: ../examples/expiration.py
    :start-line: 2
    :end-line: 3

.. admonition:: Example code
    :class: toggle

    .. literalinclude:: ../examples/expiration.py
        :lines: 1,5-


Logging requests
~~~~~~~~~~~~~~~~
.. include:: ../examples/log_requests.py
    :start-line: 2
    :end-line: 3

.. admonition:: Example code
    :class: toggle

    .. literalinclude:: ../examples/log_requests.py
        :lines: 1,5-


Converting an old cache
~~~~~~~~~~~~~~~~~~~~~~~
.. include:: ../examples/convert_cache.py
    :start-line: 2
    :end-line: 4

.. admonition:: Example code
    :class: toggle

    .. literalinclude:: ../examples/convert_cache.py
        :lines: 1,6-


