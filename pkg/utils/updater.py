
def update_all():
    """使用dulwich更新源码"""
    try:
        import dulwich
    except ModuleNotFoundError:
        raise Exception("dulwich模块未安装,请查看 https://github.com/RockChinQ/QChatGPT/issues/77")
    try:
        from dulwich import porcelain
        repo = porcelain.open_repo('.')
        porcelain.pull(repo)
    except ModuleNotFoundError:
        raise Exception("dulwich模块未安装,请查看 https://github.com/RockChinQ/QChatGPT/issues/77")
    except dulwich.porcelain.DivergedBranches:
        raise Exception("分支不一致,自动更新仅支持master分支,请手动更新(https://github.com/RockChinQ/QChatGPT/issues/76)")
