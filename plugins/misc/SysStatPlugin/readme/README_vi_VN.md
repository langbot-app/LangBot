# SysStatPlugin

Một plugin [LangBot](https://github.com/langbot-app/langbot) để xem trạng thái hệ thống bao gồm mức sử dụng CPU, bộ nhớ và đĩa.

Lấy cảm hứng từ [sysstatqcbot](https://github.com/Soulter/sysstatqcbot)

## Tính năng

- Xem mức sử dụng bộ nhớ của tiến trình hiện tại
- Xem thông tin bộ nhớ hệ thống (tổng cộng, đã dùng, còn trống, tỷ lệ sử dụng)
- Xem thông tin CPU (thời gian người dùng, thời gian hệ thống, thời gian rảnh, tỷ lệ sử dụng)
- Xem số lõi CPU và tần số
- Xem thông tin sử dụng đĩa

## Cách sử dụng

Gửi một trong các lệnh sau tới bot:

```
!sysstat
```

Bot sẽ trả lời bằng thông tin trạng thái hệ thống hiện tại.

## Ví dụ đầu ra

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
