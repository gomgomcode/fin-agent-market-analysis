class BeautifulSoup:
    def __init__(self, *args, **kwargs):
        self.content = args[0] if args else ''
    def select(self, *args, **kwargs):
        return []
    def select_one(self, *args, **kwargs):
        return None
    def find(self, *args, **kwargs):
        return None
