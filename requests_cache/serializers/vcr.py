"""Utilities to export responses to a format compatible with VCR-based libraries, including
`vcrpy <https://github.com/kevin1024/vcrpy>`_ and `betamax <https://github.com/betamaxpy/betamax>`_.
"""
from __future__ import annotations

from os import makedirs
from os.path import abspath, dirname, expanduser, join
from typing import TYPE_CHECKING, Any, Dict, Iterable
from urllib.parse import urlparse

from .. import __version__
from ..models import CachedResponse
from .preconf import yaml_preconf_stage

if TYPE_CHECKING:
    from ..backends import BaseCache


def to_vcr_cassette(cache: BaseCache, path: str):
    """Export cached responses to a VCR-compatible YAML file (cassette)

    Args:
        cache: Cache instance containing response data to export
        path: Path for new cassette file
    """

    responses = cache.responses.values()
    write_cassette(to_vcr_cassette_dict(responses), path)


def to_vcr_cassettes_by_host(cache: BaseCache, cassette_dir: str = '.'):
    """Export cached responses as VCR-compatible YAML files (cassettes), split into separate files
    based on request host

    Args:
        cache: Cache instance containing response data to export
        cassette_dir: Base directory for cassette library
    """
    responses = cache.responses.values()
    for host, cassette in to_vcr_cassette_dicts_by_host(responses).items():
        write_cassette(cassette, join(cassette_dir, f'{host}.yml'))


def to_vcr_cassette_dict(responses: Iterable[CachedResponse]) -> Dict:
    """Convert responses to a VCR cassette dict"""
    return {
        'http_interactions': [to_vcr_episode(r) for r in responses],
        'recorded_with': f'requests-cache {__version__}',
    }


def to_vcr_episode(response: CachedResponse) -> Dict:
    """Convert a single response to a VCR-compatible response ("episode") dict"""
    # Do most of the work with cattrs + default YAML conversions
    response_dict = yaml_preconf_stage.dumps(response)

    def _to_multidict(d):
        return {k: [v] for k, v in d.items()}

    # Translate requests.Response structure into VCR format
    return {
        'request': {
            'body': response_dict['request']['body'],
            'headers': _to_multidict(response_dict['request']['headers']),
            'method': response_dict['request']['method'],
            'uri': response_dict['request']['url'],
        },
        'response': {
            'body': {'string': response_dict['_content'], 'encoding': response_dict['encoding']},
            'headers': _to_multidict(response_dict['headers']),
            'status': {'code': response_dict['status_code'], 'message': response_dict['reason']},
            'url': response_dict['url'],
        },
        'recorded_at': response_dict['created_at'],
    }


def to_vcr_cassette_dicts_by_host(responses: Iterable[CachedResponse]) -> Dict[str, Dict]:
    responses_by_host: Dict[str, Any] = {}
    for response in responses:
        host = urlparse(response.request.url).netloc
        responses_by_host.setdefault(host, [])
        responses_by_host[host].append(response)
    return {host: to_vcr_cassette_dict(responses) for host, responses in responses_by_host.items()}


def write_cassette(cassette, path):
    import yaml

    path = abspath(expanduser(path))
    makedirs(dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(yaml.safe_dump(cassette))
