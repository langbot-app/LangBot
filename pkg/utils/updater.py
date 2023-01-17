import datetime

import pkg.utils.context


def check_dulwich_closure():
    try:
        import pkg.utils.pkgmgr
        pkg.utils.pkgmgr.ensure_dulwich()
    except:
        pass

    try:
        import dulwich
    except ModuleNotFoundError:
        raise Exception("dulwich模块未安装,请查看 https://github.com/RockChinQ/QChatGPT/issues/77")


def update_all() -> bool:
    """使用dulwich更新源码"""
    check_dulwich_closure()
    import dulwich
    try:
        before_commit_id = get_current_commit_id()
        from dulwich import porcelain
        repo = porcelain.open_repo('.')
        porcelain.pull(repo)

        change_log = ""

        for entry in repo.get_walker():
            if str(entry.commit.id)[2:-1] == before_commit_id:
                break
            tz = datetime.timezone(datetime.timedelta(hours=entry.commit.commit_timezone // 3600))
            dt = datetime.datetime.fromtimestamp(entry.commit.commit_time, tz)
            change_log += dt.strftime('%Y-%m-%d %H:%M:%S') + " [" + str(entry.commit.message, encoding="utf-8").strip()+"]\n"

        if change_log != "":
            pkg.utils.context.get_qqbot_manager().notify_admin("代码拉取完成,更新内容如下:\n"+change_log)
            return True
        else:
            return False
    except ModuleNotFoundError:
        raise Exception("dulwich模块未安装,请查看 https://github.com/RockChinQ/QChatGPT/issues/77")
    except dulwich.porcelain.DivergedBranches:
        raise Exception("分支不一致,自动更新仅支持master分支,请手动更新(https://github.com/RockChinQ/QChatGPT/issues/76)")


def is_repo(path: str) -> bool:
    """检查是否是git仓库"""
    check_dulwich_closure()

    from dulwich import porcelain
    try:
        porcelain.open_repo(path)
        return True
    except:
        return False



def get_remote_url(repo_path: str) -> str:
    """获取远程仓库地址"""
    check_dulwich_closure()

    from dulwich import porcelain
    repo = porcelain.open_repo(repo_path)
    return str(porcelain.get_remote_repo(repo, "origin")[1])


def get_current_version_info() -> str:
    """获取当前版本信息"""
    check_dulwich_closure()

    from dulwich import porcelain

    repo = porcelain.open_repo('.')

    version_str = ""

    for entry in repo.get_walker():
        version_str += "提交编号: "+str(entry.commit.id)[2:9] + "\n"
        tz = datetime.timezone(datetime.timedelta(hours=entry.commit.commit_timezone // 3600))
        dt = datetime.datetime.fromtimestamp(entry.commit.commit_time, tz)
        version_str += "时间: "+dt.strftime('%m-%d %H:%M:%S') + "\n"
        version_str += "说明: "+str(entry.commit.message, encoding="utf-8").strip() + "\n"
        version_str += "提交作者: '" + str(entry.commit.author)[2:-1] + "'"
        break

    return version_str


def get_commit_id_and_time_and_msg() -> str:
    """获取当前提交id和时间和提交信息"""
    check_dulwich_closure()

    from dulwich import porcelain

    repo = porcelain.open_repo('.')

    for entry in repo.get_walker():
        tz = datetime.timezone(datetime.timedelta(hours=entry.commit.commit_timezone // 3600))
        dt = datetime.datetime.fromtimestamp(entry.commit.commit_time, tz)
        return str(entry.commit.id)[2:9] + " " + dt.strftime('%Y-%m-%d %H:%M:%S') + " [" + str(entry.commit.message, encoding="utf-8").strip()+"]"


def get_current_commit_id() -> str:
    """检查是否有新版本"""
    check_dulwich_closure()

    from dulwich import porcelain

    repo = porcelain.open_repo('.')
    current_commit_id = ""
    for entry in repo.get_walker():
        current_commit_id = str(entry.commit.id)[2:-1]
        break

    return current_commit_id


def is_new_version_available() -> bool:
    """检查是否有新版本"""
    check_dulwich_closure()

    from dulwich import porcelain

    repo = porcelain.open_repo('.')
    fetch_res = porcelain.ls_remote(porcelain.get_remote_repo(repo, "origin")[1])

    current_commit_id = get_current_commit_id()

    latest_commit_id = str(fetch_res[b'HEAD'])[2:-1]

    return current_commit_id != latest_commit_id
