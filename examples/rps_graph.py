#!/usr/bin/env python
"""
This example displays a graph of request rates over time. Requests are continuously sent to URLs
randomly picked from a fixed number of possible URLs. This demonstrates how average request rate
increases as the proportion of cached requests increases.

Try running this example with different cache settings and URLs to see how the graph changes.
"""
from random import randint
from time import time

from rich.live import Live
from rich.progress import BarColumn, MofNCompleteColumn, Progress
from rich.table import Table

from requests_cache import CachedSession

N_UNIQUE_REQUESTS = 200


class RPSProgress(Progress):
    """Display a bar chart of requests per second"""

    def __init__(self, interval: int = 1, scale: int = 500, **kwargs):
        super().__init__(BarColumn(), '{task.completed}', **kwargs)
        self.current_task = None
        self.interval = interval
        self.interval_start = None
        self.scale = scale
        self.total_requests = 0
        self.next_interval()

    def next_interval(self):
        """Create a new task to draw the next line on the bar chart"""
        self.current_task = self.add_task('barchart_line', total=self.scale)
        self.interval_start = time()

    def count_request(self):
        if time() - self.interval_start >= self.interval:
            self.next_interval()
        self.advance(self.current_task)
        self.total_requests += 1


class CacheRPSProgress:
    """Track requests per second plus cache size in a single live view"""

    def __init__(self, n_unique_requests: int = 100):
        self.rps_progress = RPSProgress()
        self.cache_progress = Progress(
            BarColumn(complete_style='blue'),
            '[cyan]Requests cached:',
            MofNCompleteColumn(),
        )
        header = Progress(BarColumn(), '[cyan]Requests per second')
        header.add_task('')
        self.cache_task = self.cache_progress.add_task('', total=n_unique_requests)
        self.n_unique_requests = n_unique_requests
        self.start_time = time()

        self.table = Table.grid()
        self.table.add_row(header)
        self.table.add_row(self.rps_progress)
        self.table.add_row(self.cache_progress)
        self.live = Live(self.table, refresh_per_second=10)

    def __enter__(self):
        """Start live view on ctx enter"""
        self.live.__enter__()
        self.log(
            '[cyan]Measuring request rate with '
            f'[white]{self.n_unique_requests}[cyan] total unique requests'
        )
        self.log('[cyan]Press [white]Ctrl+C[cyan] to exit')
        return self

    def __exit__(self, *args):
        """Show stats on ctx exit"""
        self.live.__exit__(*args)
        elapsed = time() - self.start_time
        self.log(
            f'[cyan]Sent a total of [white]{self.total_requests}[cyan] '
            f'requests in [white]{elapsed:.2f}[cyan] seconds '
        )

        self.log(f'[cyan]Average: [white]{int(self.total_requests/elapsed)}[cyan] requests/second')

    @property
    def total_requests(self):
        return self.rps_progress.total_requests

    def count_request(self):
        self.rps_progress.count_request()

    def update_cache_size(self, size: int):
        self.cache_progress.update(self.cache_task, completed=size)

    def log(self, msg: str):
        self.cache_progress.log(msg)


def test_rps(session):
    session.cache.clear()

    # Send a request to one of a fixed number of unique URLs
    def random_request():
        request_number = randint(1, N_UNIQUE_REQUESTS)
        session.get(f'https://httpbin.org/get?page={request_number}')

    # Show request rate over time and total cached (unexpired) requests
    with CacheRPSProgress(N_UNIQUE_REQUESTS) as progress:
        while True:
            try:
                random_request()
                progress.count_request()
                progress.update_cache_size(session.cache.responses.count(expired=False))
            except KeyboardInterrupt:
                break


if __name__ == '__main__':
    session = CachedSession(use_temp=True, expire_after=30)
    test_rps(session)
