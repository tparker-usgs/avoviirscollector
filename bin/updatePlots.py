import seaborn as sns
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sqlite3
import datetime
import matplotlib
import cStringIO
import pycurl

DB_FILE="/Users/tparker/pytroll/gina.db"

# sns.set(style="whitegrid", palette="muted")
#
# # Load the example iris dataset
# iris = sns.load_dataset("iris")
#
# # "Melt" the dataset to "long-form" or "tidy" representation
# iris = pd.melt(iris, "species", var_name="measurement")
#
# # Draw a categorical scatterplot to show each observation
# sns.swarmplot(x="measurement", y="value", hue="species", data=iris)


def main():
    conn = sqlite3.connect(DB_FILE, detect_types=sqlite3.PARSE_DECLTYPES)

    query = "SELECT * FROM sighting;"
    df = pd.read_sql_query(query, conn)
    df['proctime'] = df['proc_date'] - df['granule_date']
    print(df.dtypes)

    # proctime = pd.Series(df['proctime'], index=df['granule_date'])
    proctime = pd.Series(df['proctime'], index=df['granule_date'])
    print(df['proctime' ])
    proctime.plot()

    proctime.show()
    conn.close()

if __name__ == "__main__":
    main()
