def retry(*args, **kwargs):
    def decorator(fn):
        return fn
    return decorator

def stop_after_attempt(*args, **kwargs):
    pass


def wait_exponential(*args, **kwargs):
    pass


def retry_if_result(*args, **kwargs):
    return lambda x: False
