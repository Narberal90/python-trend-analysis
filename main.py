import subprocess

from analysis import analyze_data


def run_spider():
    subprocess.run(["scrapy", "runspider", "job_stats/spiders/jobs.py"])


if __name__ == "__main__":
    print("Running Scrapy spider...")
    run_spider()

    print("Analyzing data and generating plot...")
    analyze_data()
