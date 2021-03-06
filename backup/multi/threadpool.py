import concurrent.futures


class ThreadPool:
    """Custom interface for an thread pool executor."""

    def __init__(self, num_threads):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=num_threads)
        self.num_threads = num_threads

    def add_task(self, func, *args, **kwargs) -> concurrent.futures.Future:
        return self.executor.submit(func, *args, **kwargs)

    def wait(self, futures: list):
        for future in futures:
            future.result(None)  # wait for every future
