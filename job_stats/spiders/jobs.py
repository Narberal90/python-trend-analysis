import csv
import time

import scrapy
import yaml
from scrapy.http import Response
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotInteractableException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from job_stats.settings import USER_AGENT


class JobsSpider(scrapy.Spider):
    name = "jobs"
    allowed_domains = ["jobs.dou.ua"]

    start_urls = [
        {"url": "https://jobs.dou.ua/vacancies/?category=Python&exp=0-1"},
        {"url": "https://jobs.dou.ua/vacancies/?category=Python&exp=1-3"},
    ]

    def __init__(self):
        super().__init__()
        self.load_tech_keywords()
        self.experience_data = {}
        self.initialize_webdriver()
        self.vacancy_count = 0

    def load_tech_keywords(self):
        with open("tech_keywords.yaml", "r") as f:
            self.tech_keywords = yaml.safe_load(f)["keywords"]

    def initialize_webdriver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument(
            f"user-agent={USER_AGENT}"
        )
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

    def start_requests(self):
        for entry in self.start_urls:
            yield scrapy.Request(url=entry["url"], callback=self.parse)

    def parse(self, response: Response, **kwargs):
        self.load_full_page(response)
        for link in self.get_vacancy_links():
            yield response.follow(
                link.get_attribute("href"), callback=self.parse_details
            )

    def load_full_page(self, response):
        self.driver.get(response.url)
        time.sleep(3)
        while self.click_more_button():
            time.sleep(2)

    def click_more_button(self):
        try:
            more_button = (
                WebDriverWait(self.driver, 2)
                .until(
                    ec.presence_of_element_located(
                        (By.CLASS_NAME, "more-btn")
                    )
                )
                .find_element(By.TAG_NAME, "a")
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView(true)",
                more_button
            )

            if (
                    more_button.is_displayed()
                    and "disabled" not in more_button.get_attribute("class")
            ):
                more_button.click()
                time.sleep(2)
                return True
        except (
                NoSuchElementException,
                ElementNotInteractableException,
                TimeoutException,
        ):
            pass
        return False

    def get_vacancy_links(self):
        return self.driver.find_elements(By.CSS_SELECTOR, "a.vt")

    def parse_details(self, response: Response):
        self.vacancy_count += 1
        self.logger.info(f"Vacancy count: {self.vacancy_count}")
        vacancy_text = " ".join(response.css(".b-typo").getall()).lower()
        for keyword in self.tech_keywords:
            if keyword in vacancy_text:
                if keyword not in self.experience_data:
                    self.experience_data[keyword] = 1
                else:
                    self.experience_data[keyword] += 1

    def close(self, reason):
        sorted_keywords = sorted(
            self.experience_data.items(), key=lambda x: x[1], reverse=True
        )

        fieldnames = [keyword for keyword, _ in sorted_keywords]

        with open(
                "data/tech_skills.csv", mode="w", newline="", encoding="utf-8"
        ) as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            csv_writer.writeheader()

            row = {
                keyword: self.experience_data.get(keyword, 0)
                for keyword in fieldnames
            }
            csv_writer.writerow(row)

        self.driver.quit()
