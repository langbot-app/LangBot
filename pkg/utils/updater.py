import datetime
import logging
import os.path

import requests
import json

import pkg.utils.constants
import pkg.utils.network as network


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


def pull_latest(repo_path: str) -> bool:
    """拉取最新代码"""
    check_dulwich_closure()

    from dulwich import porcelain

    repo = porcelain.open_repo(repo_path)
    porcelain.pull(repo)

    return True


def is_newer(new_tag: str, old_tag: str):
    """判断版本是否更新，忽略第四位版本和第一位版本"""
    if new_tag == old_tag:
        return False

    new_tag = new_tag.split(".")
    old_tag = old_tag.split(".")
    
    # 判断主版本是否相同
    if new_tag[0] != old_tag[0]:
        return False

    if len(new_tag) < 4:
        return True

    # 合成前三段，判断是否相同
    new_tag = ".".join(new_tag[:3])
    old_tag = ".".join(old_tag[:3])

    return new_tag != old_tag


def get_release_list() -> list:
    """获取发行列表"""
    rls_list_resp = requests.get(
        url="https://api.github.com/repos/RockChinQ/QChatGPT/releases",
        proxies=network.wrapper_proxies()
    )

    rls_list = rls_list_resp.json()

    return rls_list


def get_current_tag() -> str:
    """获取当前tag"""
    current_tag = pkg.utils.constants.semantic_version
    if os.path.exists("current_tag"):
        with open("current_tag", "r") as f:
            current_tag = f.read()

    return current_tag


def compare_version_str(v0: str, v1: str) -> int:
    """比较两个版本号"""

    # 删除版本号前的v
    if v0.startswith("v"):
        v0 = v0[1:]
    if v1.startswith("v"):
        v1 = v1[1:]

    v0:list = v0.split(".")
    v1:list = v1.split(".")

    # 如果两个版本号节数不同，把短的后面用0补齐
    if len(v0) < len(v1):
        v0.extend(["0"]*(len(v1)-len(v0)))
    elif len(v0) > len(v1):
        v1.extend(["0"]*(len(v0)-len(v1)))

    # 从高位向低位比较
    for i in range(len(v0)):
        if int(v0[i]) > int(v1[i]):
            return 1
        elif int(v0[i]) < int(v1[i]):
            return -1
    
    return 0


def update_all(cli: bool = False) -> bool:
    """检查更新并下载源码"""
    current_tag = get_current_tag()

    rls_list = get_release_list()

    latest_rls = {}
    rls_notes = []
    latest_tag_name = ""
    for rls in rls_list:
        rls_notes.append(rls['name'])  # 使用发行名称作为note
        if latest_tag_name == "":
            latest_tag_name = rls['tag_name']

        if rls['tag_name'] == current_tag:
            break

        if latest_rls == {}:
            latest_rls = rls
    if not cli:
        logging.info("更新日志: {}".format(rls_notes))
    else:
        print("更新日志: {}".format(rls_notes))

    if latest_rls == {} and not is_newer(latest_tag_name, current_tag):  # 没有新版本
        return False

    # 下载最新版本的zip到temp目录
    if not cli:
        logging.info("开始下载最新版本: {}".format(latest_rls['zipball_url']))
    else:
        print("开始下载最新版本: {}".format(latest_rls['zipball_url']))
    zip_url = latest_rls['zipball_url']
    zip_resp = requests.get(
        url=zip_url,
        proxies=network.wrapper_proxies()
    )
    zip_data = zip_resp.content

    # 检查temp/updater目录
    if not os.path.exists("temp"):
        os.mkdir("temp")
    if not os.path.exists("temp/updater"):
        os.mkdir("temp/updater")
    with open("temp/updater/{}.zip".format(latest_rls['tag_name']), "wb") as f:
        f.write(zip_data)

    if not cli:
        logging.info("下载最新版本完成: {}".format("temp/updater/{}.zip".format(latest_rls['tag_name'])))
    else:
        print("下载最新版本完成: {}".format("temp/updater/{}.zip".format(latest_rls['tag_name'])))

    # 解压zip到temp/updater/<tag_name>/
    import zipfile
    # 检查目标文件夹
    if os.path.exists("temp/updater/{}".format(latest_rls['tag_name'])):
        import shutil
        shutil.rmtree("temp/updater/{}".format(latest_rls['tag_name']))
    os.mkdir("temp/updater/{}".format(latest_rls['tag_name']))
    with zipfile.ZipFile("temp/updater/{}.zip".format(latest_rls['tag_name']), 'r') as zip_ref:
        zip_ref.extractall("temp/updater/{}".format(latest_rls['tag_name']))

    # 覆盖源码
    source_root = ""
    # 找到temp/updater/<tag_name>/中的第一个子目录路径
    for root, dirs, files in os.walk("temp/updater/{}".format(latest_rls['tag_name'])):
        if root != "temp/updater/{}".format(latest_rls['tag_name']):
            source_root = root
            break

    # 覆盖源码
    import shutil
    for root, dirs, files in os.walk(source_root):
        # 覆盖所有子文件子目录
        for file in files:
            src = os.path.join(root, file)
            dst = src.replace(source_root, ".")
            if os.path.exists(dst):
                os.remove(dst)

            # 检查目标文件夹是否存在
            if not os.path.exists(os.path.dirname(dst)):
                os.makedirs(os.path.dirname(dst))
            # 检查目标文件是否存在
            if not os.path.exists(dst):
                # 创建目标文件
                open(dst, "w").close()

            shutil.copy(src, dst)

    # 把current_tag写入文件
    current_tag = latest_rls['tag_name']
    with open("current_tag", "w") as f:
        f.write(current_tag)

    # 通知管理员
    if not cli:
        import pkg.utils.context
        pkg.utils.context.get_qqbot_manager().notify_admin("已更新到最新版本: {}\n更新日志:\n{}\n完整的更新日志请前往 https://github.com/RockChinQ/QChatGPT/releases 查看".format(current_tag, "\n".join(rls_notes[:-1])))
    else:
        print("已更新到最新版本: {}\n更新日志:\n{}\n完整的更新日志请前往 https://github.com/RockChinQ/QChatGPT/releases 查看".format(current_tag, "\n".join(rls_notes[:-1])))
    return True


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
    rls_list = get_release_list()
    current_tag = get_current_tag()
    for rls in rls_list:
        if rls['tag_name'] == current_tag:
            return rls['name'] + "\n" + rls['body']
    return "未知版本"


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
    # 从github获取release列表
    rls_list = get_release_list()
    if rls_list is None:
        return False

    # 获取当前版本
    current_tag = get_current_tag()

    # 检查是否有新版本
    latest_tag_name = ""
    for rls in rls_list:
        if latest_tag_name == "":
            latest_tag_name = rls['tag_name']
            break

    return is_newer(latest_tag_name, current_tag)


def get_rls_notes() -> list:
    """获取更新日志"""
    # 从github获取release列表
    rls_list = get_release_list()
    if rls_list is None:
        return None

    # 获取当前版本
    current_tag = get_current_tag()

    # 检查是否有新版本
    rls_notes = []
    for rls in rls_list:
        if rls['tag_name'] == current_tag:
            break

        rls_notes.append(rls['name'])

    return rls_notes


if __name__ == "__main__":
    update_all()
