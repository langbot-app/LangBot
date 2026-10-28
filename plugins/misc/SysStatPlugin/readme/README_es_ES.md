# SysStatPlugin

Un plugin de [LangBot](https://github.com/langbot-app/langbot) para ver el estado del sistema, incluyendo CPU, memoria y uso de disco.

Inspirado por [sysstatqcbot](https://github.com/Soulter/sysstatqcbot)

## Características

- Ver el uso de memoria del proceso actual
- Ver información de memoria del sistema (total, usada, libre, porcentaje de uso)
- Ver información de la CPU (tiempo de usuario, tiempo de sistema, tiempo de inactividad, porcentaje de uso)
- Ver el número de núcleos y la frecuencia de la CPU
- Ver información de uso del disco

## Uso

Envía uno de los siguientes comandos al bot:

```
!sysstat
```

El bot responderá con la información actual del estado del sistema.

## Ejemplo de Salida

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
