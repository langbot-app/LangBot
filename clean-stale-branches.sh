#!/bin/bash

# 获取当前时间的Unix时间戳
current_time=$(date +%s)

# 遍历所有本地分支
for branch in $(git branch --format='%(refname:short)'); do
  # 获取分支最后一次编辑的时间的Unix时间戳
  echo "Check $branch"
  last_commit_time=$(git reflog show --date=unix "$branch" | grep -o '@{[0-9]\+}' | head -n 1 | awk -F '[{}]' '{print $2}')

  # 计算时间差
  time_diff=$((current_time - last_commit_time))
  
  # 如果时间差大于一周（7天），则删除这个分支
  if [ $time_diff -gt $((7*24*60*60)) ]; then
    days=$((time_diff / (24*60*60)))
    echo "Deleting branch '$branch' (last edited $days days ago)"
    # 确认
    confirm="n"
    read -p "Are you sure? (y/n) " confirm
    if [ "$confirm" != "y" ]; then
      continue
    fi
    git branch -D "$branch"
  fi
  echo ""
done
