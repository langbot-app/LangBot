import asyncio


asciiart = r"""
  ___   ___ _         _    ___ ___ _____ 
 / _ \ / __| |_  __ _| |_ / __| _ \_   _|
| (_) | (__| ' \/ _` |  _| (_ |  _/ | |  
 \__\_\\___|_||_\__,_|\__|\___|_|   |_|  
"""

if __name__ == '__main__':
    print(asciiart)

    from pkg.core import boot
    asyncio.run(boot.main())
