import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os


def analyze_data():
    csv_path = "data/tech_skills.csv"
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        technologies = df.columns
        counts = df.iloc[0]

        sns.set_theme(style="darkgrid")
        plt.figure(figsize=(14, 6))
        plt.bar(technologies, counts, color="skyblue")

        plt.ylabel("Count")
        plt.xlabel("Technology")
        plt.title("Count by Technology")
        plt.xticks(rotation=75)

        plt.savefig("visualizations/technology_trend.png")
        plt.show()
    else:
        print("CSV file not found. Please ensure the spider ran successfully and saved the file.")



