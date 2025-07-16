class RequestException(Exception):
    pass

class exceptions:
    RequestException = RequestException

def get(url, *args, **kwargs):
    raise RequestException('Network access disabled')

class Response:
    def __init__(self, status_code=200, content=b''):
        self.status_code = status_code
        self.content = content
