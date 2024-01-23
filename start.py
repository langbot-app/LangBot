import asyncio

from pkg.boot import boot


if __name__ == '__main__':
    asyncio.run(boot.main())
