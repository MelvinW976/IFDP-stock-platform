from config import CLOUD_CONFIGURE, PROCESS_CNT
from multiprocessing import Pool
import pandas as pd
import yfinance as yf

"""
Import S&P 500 ticker and name
"""
df_sp500 = pd.read_csv('sp500.csv')
tickers = ' '.join(df_sp500['Symbol'])

def fetch_from_yahoo(idx):
    for ticker in df_sp500['Symbol'][idx[0]:idx[1]]:
        pass


def fetch_from_yahoo_parallel():
    """
    Use muti-process to enhance the performance of a fetching process
    """
    list_idx = []
    length_each_process = len(df_sp500) // PROCESS_CNT
    for i in range(PROCESS_CNT):
        list_idx += [i*length_each_process,  
                        min((i+1)*length_each_process, len(df_sp500))],
    with Pool(PROCESS_CNT) as p:
        p.map(fetch_from_yahoo, list_idx)

def fetch_data_all():
    """
    Fetch all the historical data of the stock in pool
    """
    data = yf.download(  # or pdr.get_data_yahoo(...
        # tickers list or string as well
        tickers = tickers,

        # use "period" instead of start/end
        # valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
        # (optional, default is '1mo')
        period = "7d",

        # fetch data by interval (including intraday if period < 60 days)
        # valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
        # (optional, default is '1d')
        interval = "1d",

        # group by ticker (to access via data['SPY'])
        # (optional, default is 'column')
        group_by = 'ticker',

        # adjust all OHLC automatically
        # (optional, default is False)
        auto_adjust = True,

        # download pre/post regular market hours data
        # (optional, default is False)
        prepost = True,

        # use threads for mass downloading? (True/False/Integer)
        # (optional, default is True)
        threads = True,

        # proxy URL scheme use use when downloading?
        # (optional, default is None)
        proxy = None
    )
    return data

def fetch_all_tickers():
    """
    return dataframe Symbols
    """
    return df_sp500['Symbol']

if __name__ == '__main__':
    print("FETCHING DATA FROM YAHOO")
    # fetch_from_yahoo_parallel()
    # fetch_from_yahoo([0, len(df_sp500['Symbol'])-1])
    # fetch_data()