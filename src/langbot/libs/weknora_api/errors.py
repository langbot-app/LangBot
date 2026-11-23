class WeKnoraAPIError(Exception):
    """WeKnora API 请求失败"""

    def __init__(self, message: str = ''):
        self.message = message
        super().__init__(self.message)
