import csv

import scrapy
import yaml
from scrapy.http import Response, HtmlResponse
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from job_stats.settings import USER_AGENT


class SeleniumLoader:
    def __init__(self, driver):
        self.driver = driver

    def load_full_page(self, url):
        self.driver.get(url)
        max_retries = 10
        retries = 0
        self.last_vacancy_count = 0

        while retries < max_retries:
            vacancies = self.driver.find_elements(By.CSS_SELECTOR, "a.vt")
            current_vacancy_count = len(vacancies)

            if current_vacancy_count == self.last_vacancy_count:
                print("No new vacancies loaded.")
                break

            self.last_vacancy_count = current_vacancy_count

            if not self.click_more_button():
                print("No more button to click.")
                break

            retries += 1

        print(f"Loaded {self.last_vacancy_count} vacancies.")

    def click_more_button(self):
        try:
            more_button = WebDriverWait(self.driver, 5).until(
                ec.presence_of_element_located((By.CLASS_NAME, "more-btn"))
            ).find_element(By.TAG_NAME, "a")

            if (
                    more_button.is_displayed()
                    and "disabled" not in more_button.get_attribute("class")
            ):
                self.driver.execute_script("arguments[0].scrollIntoView(true)", more_button)
                more_button.click()
                print("Button clicked!")

                WebDriverWait(self.driver, 10).until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.vt")) > self.last_vacancy_count
                )
                return True
            else:
                print("Button is not clickable or is disabled.")
                return False
        except TimeoutException:
            print("More button not found or not clickable.")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False


class DataProcessor:
    def __init__(self, tech_keywords):
        self.tech_keywords = tech_keywords
        self.experience_data = {}

    def process_vacancy(self, vacancy_text):
        vacancy_text = vacancy_text.lower()
        matched_keywords = set(self.tech_keywords).intersection(vacancy_text.split())
        for keyword in matched_keywords:
            self.experience_data[keyword] = self.experience_data.get(keyword, 0) + 1

    def save_csv(self):
        sorted_keywords = sorted(
            self.experience_data.items(), key=lambda x: x[1], reverse=True
        )
        with open("data/tech_skills.csv", mode="w", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.DictWriter(
                csv_file, fieldnames=[k for k, _ in sorted_keywords]
            )
            csv_writer.writeheader()
            csv_writer.writerow(
                {k: self.experience_data[k] for k in dict(sorted_keywords)}
            )


class JobsSpider(scrapy.Spider):
    name = "jobs"
    allowed_domains = ["jobs.dou.ua"]

    start_urls = [
        {"url": "https://jobs.dou.ua/vacancies/?category=Python&exp=0-1"},
        {"url": "https://jobs.dou.ua/vacancies/?category=Python&exp=1-3"},
    ]

    def __init__(self):
        super().__init__()
        self.tech_keywords = self.load_tech_keywords()
        self.data_processor = DataProcessor(self.tech_keywords)
        self._driver = None
        self.vacancy_count = 0

    def load_tech_keywords(self):
        try:
            with open("tech_keywords.yaml", "r") as f:
                return yaml.safe_load(f)["keywords"]
        except FileNotFoundError:
            self.logger.error("tech_keywords.yaml file not found.")
            return []
        except KeyError:
            self.logger.error("Invalid format in tech_keywords.yaml.")
            return []

    @property
    def driver(self):
        if not self._driver:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument(f"user-agent={USER_AGENT}")
            self._driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), options=chrome_options
            )
        return self._driver

    def start_requests(self):
        for entry in self.start_urls:
            yield scrapy.Request(url=entry["url"], callback=self.parse)

    def parse(self, response: Response, **kwargs):
        selenium_loader = SeleniumLoader(self.driver)
        selenium_loader.load_full_page(response.url)

        html = self.driver.page_source
        response = HtmlResponse(url=self.driver.current_url, body=html, encoding='utf-8')

        links = response.css("a.vt::attr(href)").getall()
        for link in links:
            yield response.follow(link, callback=self.parse_details)

    def parse_details(self, response: Response):
        self.vacancy_count += 1
        self.logger.info(f"Vacancy count: {self.vacancy_count}")

        vacancy_text = " ".join(response.css(".b-typo *::text").getall())
        self.data_processor.process_vacancy(vacancy_text)

        self.data_processor.save_csv()

    def close(self, reason):
        if self._driver:
            self._driver.quit()
