<!-- TODO: Logging, tracebacks, submitting issues, etc. -->
# Troubleshooting

## Potential Issues
- See {ref}`monkeypatch-issues` for issues specific to {py:func}`.install_cache`
- New releases of `requests`, `urllib3` or `requests-cache` itself may change response data and be
  be incompatible with previously cached data (see issues
  [#56](https://github.com/reclosedev/requests-cache/issues/56) and
  [#102](https://github.com/reclosedev/requests-cache/issues/102)).
  In these cases, the cached data will simply be invalidated and a new response will be fetched.
