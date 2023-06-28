import asyncio
import logging
import re

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from fake_headers import Headers
from datetime import datetime


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


class Parser:
    def __init__(self):
        self.rst_url = 'https://www.rst.gov.ru'

    async def get_response_text(self, url: str):
        async with ClientSession() as session:
            headers = Headers().generate()
            async with session.get(url=url, headers=headers) as response:
                if response.ok:
                    return await response.text()

    async def get_soup(self, response_text):
        soup = BeautifulSoup(response_text, 'lxml')
        return soup

    async def get_notices_tbl(self, url_tail: str = ''):
        """Получаем таблицу с уведомленими о сводах правил.
        Если такое правило есть в БД, то на следующую страницу не идём.
        Если нет - то проходим пагинацию."""
        notice_dict = {}  # сюда будут собираться данные по отдельному своду
        page_dict = {}
        url = f"{self.rst_url}{url_tail}"
        response = await self.get_response_text(url=url)
        soup = await self.get_soup(response)
        pages = soup.find("div", class_="gost-paging__count").text
        page_dict["current_page"] = int(pages.strip().split()[3])
        page_dict["all_pages"] = int(pages.strip().split()[-1])
        next_url_tail = soup.find("a", class_="button", string=re.compile("Вперед")).get("href")  # стр. Вперед
        all_notice = soup.find("tbody").find_all("tr")
        for num, notice in enumerate(all_notice, start=1):
            notice_dict['notice'] = notice.find("a").text
            notice_dict['url_tail'] = notice.find("a").get("href")  # хвост ссылки (прикрепить к self.rst_url
            notice_date = notice.find_all(class_="gost-table__cell")[1].text.strip() # 26.06.23
            dt = datetime.strptime(notice_date, '%d.%m.%y')
            notice_dict['date'] = dt.strftime("%Y-%m-%d")
            if num == 10:
                yield page_dict, notice_dict, next_url_tail
            else:
                yield page_dict, notice_dict, None

    async def get_notices_data(self, stop_flag: bool = True):
        """Получаем данные из таблицы со сводами.
        Для остановки пагинации, нужно передать stop_flag = False"""
        # tail - окончания главного url, который ведет на страницу ведомлений
        url_tail = '/portal/gost/home/activity/standardization/notification/notificationssetrules'
        current_page, all_pages = 0, 0
        while stop_flag:
            async for notice_data in self.get_notices_tbl(url_tail=url_tail):
                current_page = notice_data[0]["current_page"]
                all_pages = notice_data[0]["all_pages"]
                notice = notice_data[1]["notice"]
                notice_date = notice_data[1]["date"]
                notice_url_tail = f"{self.rst_url}{notice_data[1]['url_tail']}"
                if notice_data[2]:  # если есть ссылка на следующую страницу
                    url_tail = notice_data[2]
                yield notice, notice_date, notice_url_tail
            if current_page == all_pages:
                stop_flag = False
            await asyncio.sleep(3)
            # print(1)


async def main():
    async for data in Parser().get_notices_data():
        logging.info(data)


if __name__ == "__main__":
    asyncio.run(main())
