# SysStatPlugin

A [LangBot](https://github.com/langbot-app/langbot) plugin for viewing system status including CPU, memory, and disk usage.

Inspired by [sysstatqcbot](https://github.com/Soulter/sysstatqcbot)

## Features

- View current process memory usage
- View system memory information (total, used, free, usage percentage)
- View CPU information (user time, system time, idle time, usage percentage)
- View CPU core count and frequency
- View disk usage information

## Usage

Send one of the following commands to the bot:

```
!sysstat
```

The bot will reply with the current system status information.

## Example Output

```
====系统状态====
进程内存占用: 245.32MB
总内存: 16384.00MB
已用内存: 8192.50MB
空闲内存: 8191.50MB
内存使用率: 50.00%
用户态CPU时间: 1234.56秒
系统态CPU时间: 567.89秒
空闲CPU时间: 12345.67秒
CPU使用率: 25.50%
CPU逻辑核心数: 8
CPU物理核心数: 4
CPU当前频率: 2400.00MHz
总磁盘空间: 256.00GB
已用磁盘空间: 128.50GB
空闲磁盘空间: 127.50GB
磁盘使用率: 50.20%
============
```
