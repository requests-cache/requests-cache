# GridFS
```{image} ../_static/mongodb.png
```

[GridFS](https://docs.mongodb.com/manual/core/gridfs/) is a specification for storing large files
in MongoDB.

## Use Cases
Use this backend if you are using MongoDB and expect to store responses **larger than 16MB**. See
{py:mod}`~requests_cache.backends.mongodb` for more general info.

## API Reference
```{eval-rst}
.. automodsumm:: requests_cache.backends.gridfs
   :classes-only:
   :nosignatures:

.. automodule:: requests_cache.backends.gridfs
   :members:
   :undoc-members:
   :inherited-members:
   :show-inheritance:
```
