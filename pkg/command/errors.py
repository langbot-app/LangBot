

class CommandError(Exception):
    pass


class CommandNotFoundError(CommandError):
    pass


class CommandPrivilegeError(CommandError):
    pass