class RequesterError(Exception):
    """Base class for all Requester errors."""

    def __init__(self, message: str):
        super().__init__('模型请求失败: ' + message)
