import os
import sys
import paramiko
import time
import select


class sshClient:
    #创建一个ssh客户端，和服务器连接上，准备发消息
    def __init__(self,host,port,user,password):
        self.trans = paramiko.Transport((host, port))
        self.trans.start_client()
        self.trans.auth_password(username=user, password=password)
        self.channel = self.trans.open_session()
        self.channel.get_pty()
        self.channel.invoke_shell()

    #给服务器发送一个命令
    def sendCmd(self,cmd):
        self.channel.sendall(cmd)
        
    #接收的时候，有时候服务器处理的比较慢，需要设置一个延时等待一下。
    def recvResponse(self,timeout):
        data=b''
        while True:
            try:
                #使用select，不断的读取数据，直到没有多余的数据了，超时返回。
                readable,w,e= select.select([self.channel],[],[],timeout)
                if self.channel in readable:
                    data = self.channel.recv(1024)
                else:
                    sys.stdout.write(data.decode())
                    sys.stdout.flush()
                    return data.decode()
            except TimeoutError:
                sys.stdout.write(data.decode())
                sys.stdout.flush()
                return data.decode
    #关闭客户端
    def close(self):
        self.channel.close()
        self.trans.close()

host='host'
port=22#your port
user='root'
pwd='pass'

ssh = sshClient(host,port,user,pwd)
response = ssh.recvResponse(1)
response = ssh.sendCmd("ls\n")
ssh.sendCmd("cd /home\n")
response = ssh.recvResponse(1)
ssh.sendCmd("ls\n")
response = ssh.recvResponse(1)

ssh.close()
