"""Import libraries"""
from distutils.command.config import config
from re import A
from flask import Flask, jsonify, request
from config import CLOUD_CONFIGURE, PROCESS_CNT, BLOB_CONFIGURE
from apscheduler.schedulers.background import BackgroundScheduler
from azure.cosmos import exceptions, CosmosClient, PartitionKey
from fetch import fetch_from_yahoo_parallel, fetch_all_tickers, fetch_data_all
import numpy as np
from multiprocessing import Pool
import os, uuid
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, __version__
from azure.core.exceptions import ResourceExistsError
import pandas as pd
"""
Inialize the flask container
"""
app = Flask(__name__)

"""
Initialize Blob
"""
connect_str = BLOB_CONFIGURE['CONNECT_STR']
# Create the BlobServiceClient object which will be used to create a container client
blob_service_client = BlobServiceClient.from_connection_string(connect_str)
# Create a unique name for the container
container_name = BLOB_CONFIGURE['CONTAINER_NAME']
# Create the container
try:
    container_blob = blob_service_client.create_container(container_name)
except ResourceExistsError:
    print("Container already exists.")
    container_blob = blob_service_client.get_container_client(container_name)

"""
Initalize Cosmos db 
"""
endpoint = CLOUD_CONFIGURE['END_POINT']
key = CLOUD_CONFIGURE['KEY']
client = CosmosClient(endpoint, key)
database_name = 'Final_Project'
database = client.create_database_if_not_exists(id=database_name)
container = database.create_container_if_not_exists(
    id='stock_version1_5min', 
    partition_key=PartitionKey(path="/id"),
)




"""
Routely update the cosmos database
"""
sched = BackgroundScheduler() 
sched.add_job(fetch_from_yahoo_parallel, 'interval', minutes=1) # call update function every one minute
sched.start()

@app.route('/')
def hello_world():
    """Print 'Hello, world!' as the response body."""
    return 'Hello, world!'

@app.route('/tickers')
def tickers_list():
    """
    Return the list of all tickers supporting
    """
    return fetch_all_tickers().to_json()

@app.route('/stock')
def stock_price():
    return "Stock price"

def upload_data(df):
    for row in df.iterrows():
        row = row[1]
        key_str = row['Ticker'] + '_' + row['Time']
        val_ = [row['Open'], row['Close'], row['High'], row['Low'], row['Volume']]
        container.upsert_item(dict(id = key_str, val = val_))

@app.route('/initalize')
def initalize_database():
    """
    As the first time starting the database, we download all the previous stock data
    and syncrhonize with the current status.
    """
    data_df = fetch_data_all()
    output = data_df.to_csv (index=True, encoding = "utf-8")
    blob_client = container_blob.get_blob_client("dataset.csv")
    # upload data
    blob_client.upload_blob(output, blob_type="BlockBlob")
    # update to cloud cosmos
    with Pool(PROCESS_CNT) as p:
        p.map(upload_data, np.array_split(data_df, PROCESS_CNT))
    upload_data(data_df)

def data_preprocess(data_df):
    dfs = []
    for idx in data_df.index:
        df = data_df.loc[idx].reset_index(inplace = False)
        df['Time'] = idx
        df = df.rename(columns={df.columns[2]: 'Price', 'level_0': 'Ticker', 'level_1': 'Indicator'})
        dfs.append(df) 

    output_df = pd.concat(dfs)
    output_df = output_df.pivot_table(index = ['Time', 'Ticker'], columns = ['Indicator'], \
                                      values = ['Price'], fill_value=0).reset_index()
    output_df.columns = ['Time','Ticker','Close', 'High', 'Low', 'Open', 'Volume']
    output_df = output_df[output_df['Volume'] > 0]
    output_df = output_df.sort_values(by=['Ticker', 'Time'])
    output_df['Time'] = output_df['Time'].apply(lambda x: x.strftime('%Y-%m-%d %X'))
    return output_df

def upload_to_blob(data_df):
    output = data_df.to_csv(index=False, encoding = "utf-8")

    # Instantiate a new BlobClient
    blob_client = container_blob.get_blob_client("dataset_final.csv")
    # upload data
    blob_client.upload_blob(output, blob_type="BlockBlob", overwrite=True)

if __name__ == '__main__':
    app.run()

    # initalize_database()
    data_df = fetch_data_all()
    data_df = data_preprocess(data_df)
    upload_data(data_df)

    # upload_to_blob(data_df)

    # update to cloud cosmos
    with Pool(PROCESS_CNT) as p:
        p.map(upload_data, np.array_split(data_df, PROCESS_CNT))
    # upload_data(data_df)