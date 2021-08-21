#!/usr/bin/env python
"""
An example of benchmarking cache write speeds with semi-randomized response content

Usage:
```
python benchmark.py -b <backend name>
```
"""
from argparse import ArgumentParser
from os import urandom
from random import random
from time import perf_counter as time

import requests
from rich import print
from rich.progress import Progress

from requests_cache import CachedResponse, CachedSession

BASE_RESPONSE = requests.get('https://httpbin.org/get')
CACHE_NAME = 'rubbish_bin'
WARMUP_ITERATIONS = 100
ITERATIONS = 5000
MAX_RESPONSE_SIZE = 1024 * 350

# Defaults for DynamoDB
AWS_OPTIONS = {
    'endpoint_url': 'http://localhost:8000',
    'region_name': 'us-east-1',
    'aws_access_key_id': 'placeholder',
    'aws_secret_access_key': 'placeholder',
}


def test_write_speed(session):
    for i in range(WARMUP_ITERATIONS):
        new_response = get_randomized_response(i)
        session.cache.save_response(new_response)

    with Progress() as progress:
        task = progress.add_task('[cyan]Testing write speed...', total=ITERATIONS)
        start = time()

        for i in range(ITERATIONS):
            new_response = get_randomized_response(i)
            session.cache.save_response(new_response)
            progress.update(task, advance=1)

    elapsed = time() - start
    avg = (elapsed / ITERATIONS) * 1000
    print(f'[cyan]Elapsed: [green]{elapsed:.3f}[/] seconds (avg [green]{avg:.3f}[/] ms per write)')


def test_read_speed(session):
    keys = list(session.cache.responses.keys())
    for i in range(WARMUP_ITERATIONS):
        key = keys[i % len(keys)]
        session.cache.get_response(key)

    with Progress() as progress:
        task = progress.add_task('[cyan]Testing read speed...', total=ITERATIONS)
        start = time()

        for i in range(ITERATIONS):
            key = keys[i % len(keys)]
            session.cache.get_response(key)
            progress.update(task, advance=1)

    elapsed = time() - start
    avg = (elapsed / ITERATIONS) * 1000
    print(f'[cyan]Elapsed: [green]{elapsed:.3f}[/] seconds (avg [green]{avg:.3f}[/] ms per read)')


def get_randomized_response(i=0):
    """Get a response with randomized content"""
    new_response = CachedResponse.from_response(BASE_RESPONSE)
    n_bytes = int(random() * MAX_RESPONSE_SIZE)
    new_response._content = urandom(n_bytes)
    new_response.request.url += f'/response_{i}'
    return new_response


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-b', '--backend', default='sqlite')
    args = parser.parse_args()
    print(f'[cyan]Benchmarking {args.backend} backend')

    kwargs = {}
    if args.backend == 'dynamodb':
        kwargs = AWS_OPTIONS
    elif args.backend == 'sqlite-memory':
        args.backend = 'sqlite'
        kwargs = {'use_memory': True}

    session = CachedSession(CACHE_NAME, backend=args.backend, **kwargs)
    test_write_speed(session)
    test_read_speed(session)
