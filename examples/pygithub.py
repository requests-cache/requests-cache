#!/usr/bin/env python
"""
An example of caching [GitHub API](https://docs.github.com/en/rest) requests with
[PyGithub](https://github.com/PyGithub/PyGithub).

This example demonstrates the following features:
* {ref}`patching`: PyGithub uses `requests`, but the session it uses is not easily accessible.
  In this case, using {py:func}`.install_cache` is the easiest approach.
* {ref}`URL Patterns <url-filtering>`: Since we're using patching, this example adds an optional
  safety measure to avoid unintentionally caching any non-Github requests elsewhere in your code.
* {ref}`cache-control`: The GitHub API provides `Cache-Control` headers, so we can use those to set
  expiration.
* {ref}`conditional-requests`: The GitHub API also supports conditional requests. Even after
  responses expire, we can still make use of the cache until the remote content actually changes.
* [Rate limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting):
  The GitHub API is rate-limited at 5000 requests per hour if authenticated, or only 60 requests per
  hour otherwise. This makes caching especially useful, because cache hits and `304 Not Modified`
  responses (from conditional requests) are not counted against the rate limit.
* {ref}`inspection`: After calling some PyGithub functions, we can take a look at the cache contents
  to see the actual API requests that were sent.
* {ref}`Security <default-filter-params>`: If you use a
  [personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token),
  it will be sent to the GitHub API via the `Authorization` header. This is not something you want
  to store in the cache if your storage backend is unsecured, so `Authorization` and other common
  auth headers/params are redacted by default. This example shows how to verify this.
"""
from time import time

import requests
from github import Github

from requests_cache import DO_NOT_CACHE, get_cache, install_cache

# (Optional) Add an access token here, if you want higher rate limits and access to private repos
ACCESS_TOKEN = None

# Or add your own username here (if not using an access token)
MY_USERNAME = 'test-user'


install_cache(
    cache_control=True,
    urls_expire_after={
        '*.github.com': 360,  # Placeholder expiration; should be overridden by Cache-Control
        '*': DO_NOT_CACHE,  # Don't cache anything other than GitHub requests
    },
)


def get_user_info():
    """Display some info about your own resources on GitHub"""
    gh = Github(ACCESS_TOKEN)
    my_user = gh.get_user() if ACCESS_TOKEN else gh.get_user(MY_USERNAME)

    # Get links to all of your own repositories
    print('My repos:')
    for repo in my_user.get_repos():
        print(repo.html_url)

    # Get links to all of your own gists
    print('\nMy gists:')
    for gist in my_user.get_gists():
        print(gist.html_url)

    # Get organizations you belong to
    print('\nMy organizations:')
    for org in my_user.get_orgs():
        print(org.html_url)

    # Check how internet-famous you are
    print('\nMy followers:')
    for user in my_user.get_followers():
        print(user.login)

    # Check your API rate limit usage
    print(f'\nRate limit: {gh.rate_limiting}')


def test_non_github_requests():
    """Test that URL patterns are working, and that non-GitHub requests are not cached"""
    response = requests.get('https://httpbin.org/json')
    response = requests.get('https://httpbin.org/json')
    from_cache = getattr(response, 'from_cache', False)
    print(f'Non-GitHub requests cached: {from_cache}')
    assert not from_cache


def check_cache():
    """Check some information on cached requests"""
    # Show all the GitHub API URLs that PyGithub called
    print('\nCached URLs:')
    print('\n'.join(get_cache().urls()))

    # Make sure credentials were redacted from all responses in the cache
    response = requests.get('https://api.github.com/user/repos')
    print('\nExample cached request headers:')
    print(response.request.headers)
    for response in get_cache().responses.values():
        assert 'Authorization' not in response.request.headers


def main():
    # Send initial requests
    start = time()
    get_user_info()
    print(f'Elapsed: {time() - start:.2f} seconds')

    # Repeat the same requests and verify that your rate limit usage is unchanged
    start = time()
    get_user_info()
    print(f'Elapsed: {time() - start:.2f} seconds')

    test_non_github_requests()
    check_cache()


if __name__ == '__main__':
    main()
