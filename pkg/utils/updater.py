import time


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


def get_current_version_info() -> str:
    """获取当前版本信息"""
    try:
        import dulwich
    except ModuleNotFoundError:
        raise Exception("dulwich模块未安装,请查看 https://github.com/RockChinQ/QChatGPT/issues/77")

    from dulwich import porcelain

    repo = porcelain.open_repo('.')

    version_str = ""

    for entry in repo.get_walker():
        version_str += "提交编号: "+str(entry.commit.id)[2:9] + "\n"
        version_str += "时间: "+time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry.commit.commit_time)) + "\n"
        version_str += "说明: "+str(entry.commit.message, encoding="utf-8").strip() + "\n"
        version_str += "提交作者: '" + str(entry.commit.author)[2:-1] + "'"
        break

    return version_str
