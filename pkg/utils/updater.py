def update_all():
    try:
        from dulwich import porcelain
        repo = porcelain.open_repo('.')
        porcelain.pull(repo)
    except ModuleNotFoundError:
        raise Exception("dulwich模块未安装,请查看 https://github.com/RockChinQ/QChatGPT/issues/77")