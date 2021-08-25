# TODO: Maybe this should be a one-way conversion function instead of a full serializer?
"""YAML serializer compatible with VCR-based libraries, including `vcrpy
<https://github.com/kevin1024/vcrpy>`_ and `betamax <https://github.com/betamaxpy/betamax>`_.
"""
from os import makedirs
from os.path import abspath, dirname, expanduser, join
from typing import Any, Dict, Iterable
from urllib.parse import urlparse

from .. import __version__, get_placeholder_class
from ..models import CachedHTTPResponse, CachedRequest, CachedResponse
from .pipeline import SerializerPipeline, Stage
from .preconf import yaml_preconf_stage


def to_vcr_cassette(responses: Iterable[CachedResponse]) -> Dict:
    """Convert responses to a VCR cassette"""
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


def from_vcr_episode(cassette_dict: Dict):
    data = cassette_dict.get('interactions') or cassette_dict.get('http_interactions') or cassette_dict
    request = CachedRequest(
        body=data['request']['body'],
        headers=data['request']['headers'],
        method=data['request']['method'],
        url=data['request']['uri'],
    )
    raw_response = CachedHTTPResponse(body=data['response']['body'])  # type: ignore  # TODO: fix type hint
    return CachedResponse(
        content=data['response']['body']['string'],
        encoding=data['response']['body'].get('encoding'),
        headers=data['response']['headers'],
        raw=raw_response,
        reason=data['response']['status']['message'],
        request=request,
        status_code=data['response']['status']['code'],
        url=data['response']['url'],
    )


try:
    import yaml

    vcr_stage = Stage(dumps=to_vcr_episode, loads=from_vcr_episode)
    vcr_serializer = SerializerPipeline(
        [
            yaml_preconf_stage,
            vcr_stage,
            Stage(yaml, loads='safe_load', dumps='safe_dump'),
        ]
    )  #: VRC-compatible YAML serializer
except ImportError as e:
    yaml_serializer = get_placeholder_class(e)


# Experimental
# ------------


def save_vcr_cassette(responses: Iterable[CachedResponse], path: str):
    """Save responses as VCR-compatible YAML files"""
    _write_cassette(to_vcr_cassette(responses), path)


def save_vcr_cassettes_by_host(responses: Iterable[CachedResponse], cassette_dir: str):
    """Save responses as VCR-compatible YAML files, with one cassette per request host"""

    cassettes_by_host = _to_vcr_cassettes_by_host(responses)
    for host, cassette in cassettes_by_host.items():
        _write_cassette(cassette, join(cassette_dir, f'{host}.yml'))


def _to_vcr_cassettes_by_host(responses: Iterable[CachedResponse]) -> Dict[str, Dict]:
    responses_by_host: Dict[str, Any] = {}
    for response in responses:
        host = urlparse(response.request.url).netloc
        responses_by_host.setdefault(host, [])
        responses_by_host[host].append(response)
    return {host: to_vcr_cassette(responses) for host, responses in responses_by_host.items()}


def _write_cassette(cassette, path):
    import yaml

    path = abspath(expanduser(path))
    makedirs(dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(yaml.safe_dump(cassette))
