from datetime import datetime
from typing import Union, Optional

import asyncio
import logging as logger

import httpx

from pkg.model import AirApi, NowApi, DailyApi, HourlyApi, WarningApi, WeatherInfo, SunApi


_REQUEST_TIMEOUT = 10.0


class APIError(Exception):
    ...


class ConfigError(Exception):
    ...


class CityNotFoundError(Exception):
    ...


async def _get_data(url: str, params: dict) -> httpx.Response:
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        return await client.get(url, params=params)


def _check_response(response: httpx.Response) -> bool:
    if response.status_code == 200:
        logger.debug(f"{response.json()}")
        return True
    else:
        raise APIError(f"Response code:{response.status_code}")


class Weather:
    def __url__(self):
        self.url_geoapi = "https://geoapi.qweather.com/v2/city/"
        if self.api_type == 2 or self.api_type == 1:
            self.url_weather_api = "https://api.qweather.com/v7/weather/"
            self.url_weather_warning = "https://api.qweather.com/v7/warning/now"
            self.url_air = "https://api.qweather.com/v7/air/now"
            self.url_hourly = "https://api.qweather.com/v7/weather/24h"
            self.url_info = "https://api.qweather.com/v7/indices/1d"
            self.url_sun = 'https://api.qweather.com/v7/astronomy/sun'
            self.forecast_days = 7
            logger.info("使用标准订阅API")
        elif self.api_type == 0:
            self.url_weather_api = "https://devapi.qweather.com/v7/weather/"
            self.url_weather_warning = "https://devapi.qweather.com/v7/warning/now"
            self.url_air = "https://devapi.qweather.com/v7/air/now"
            self.url_hourly = "https://devapi.qweather.com/v7/weather/24h"
            self.url_info = "https://devapi.qweather.com/v7/indices/1d"
            self.url_sun = 'https://devapi.qweather.com/v7/astronomy/sun'
            self.forecast_days = 3
            logger.info("使用免费订阅API")
        else:
            raise ConfigError(
                "api_type 必须是为 (int)0 -> 免费订阅, (int)1 -> 标准订阅, (int)2 -> 商业版"
                f"\n当前为: ({type(self.api_type)}){self.api_type}"
            )

    def __init__(self, city_name: str, api_key: str, api_type: Union[int, str] = 0):
        self.city_name = city_name
        self.apikey = api_key
        self.api_type = int(api_type)
        self.qweather_info = '1,5,9,16'
        self.__url__()
        self.__reference = "\n请参考: https://dev.qweather.com/docs/start/status-code/"

    async def load_data(self):
        self.city_id = await self._get_city_id()
        tasks = [
            asyncio.ensure_future(coro)
            for coro in (
                self._now(),
                self._daily(),
                self._air(),
                self._warning(),
                self._hourly(),
                self._info(),
                self._sun(),
            )
        ]
        try:
            results = await asyncio.gather(*tasks)
        except BaseException:
            # Structured concurrency: the failing branch must not outlive this
            # invocation. Cancel every sibling and wait for all of them to
            # finish (each holds this call's API key) before propagating the
            # original error/cancellation.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        (
            self.now,
            self.daily,
            self.air,
            self.warning,
            self.hourly,
            self.info,
            self.sun
        ) = results
        self._data_validate()

    async def _get_city_id(self, api_type: str = "lookup"):
        res = await _get_data(
            url=self.url_geoapi + api_type,
            params={"location": self.city_name, "key": self.apikey, "number": 1},
        )

        res = res.json()
        logger.debug(res)
        if res["code"] == "404":
            raise CityNotFoundError()
        elif res["code"] != "200":
            raise APIError("错误! 错误代码: {}".format(res["code"]) + self.__reference)
        else:
            self.city_name = res["location"][0]["name"]
            return res["location"][0]["id"]

    def _data_validate(self):
        if self.now.code == "200" and self.daily.code == "200":
            pass
        else:
            raise APIError(
                "错误! 请检查配置! "
                f"错误代码: now: {self.now.code}  "
                f"daily: {self.daily.code}  "
                + "air: {}  ".format(self.air.code if self.air else "None")
                + "warning: {}".format(self.warning.code if self.warning else "None")
                + self.__reference
            )

    async def _now(self) -> NowApi:
        res = await _get_data(
            url=self.url_weather_api + "now",
            params={"location": self.city_id, "key": self.apikey},
        )
        _check_response(res)
        return NowApi(**res.json())

    async def _daily(self) -> DailyApi:
        res = await _get_data(
            url=self.url_weather_api + str(self.forecast_days) + "d",
            params={"location": self.city_id, "key": self.apikey},
        )
        _check_response(res)
        return DailyApi(**res.json())

    async def _air(self) -> AirApi:
        res = await _get_data(
            url=self.url_air,
            params={"location": self.city_id, "key": self.apikey},
        )
        _check_response(res)
        return AirApi(**res.json())

    async def _warning(self) -> Optional[WarningApi]:
        res = await _get_data(
            url=self.url_weather_warning,
            params={"location": self.city_id, "key": self.apikey},
        )
        _check_response(res)
        return None if res.json().get("code") == "204" else WarningApi(**res.json())

    async def _hourly(self) -> HourlyApi:
        res = await _get_data(
            url=self.url_hourly,
            params={"location": self.city_id, "key": self.apikey},
        )
        _check_response(res)
        return HourlyApi(**res.json())

    async def _info(self) -> WeatherInfo:
        res = await _get_data(
            url=self.url_info,
            params={"location": self.city_id, "key": self.apikey, "type": self.qweather_info, 'lang': 'zh'}
        )
        _check_response(res)
        return WeatherInfo(**res.json())

    async def _sun(self) -> SunApi:
        now = datetime.now()
        formatted_time = now.strftime('%Y%m%d')
        res = await _get_data(
            url=self.url_sun,
            params={"location": self.city_id, "key": self.apikey, "date": formatted_time, 'lang': 'zh'}
        )
        _check_response(res)
        return SunApi(**res.json())
