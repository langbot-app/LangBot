import asyncio


asciiart = r"""
  ___   ___ _         _    ___ ___ _____ 
 / _ \ / __| |_  __ _| |_ / __| _ \_   _|
| (_) | (__| ' \/ _` |  _| (_ |  _/ | |  
 \__\_\\___|_||_\__,_|\__|\___|_|   |_|  

⭐️开源地址: https://github.com/RockChinQ/QChatGPT
📖文档地址: https://q.rkcn.top
"""

if __name__ == '__main__':
    print(asciiart)

    from pkg.core import boot
    asyncio.run(boot.main())
