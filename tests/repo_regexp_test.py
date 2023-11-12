import re

repo_url = "git@github.com:RockChinQ/WebwlkrPlugin.git"

repo =  re.findall(r'(?:https?://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git|/|$)', repo_url)

print(repo)