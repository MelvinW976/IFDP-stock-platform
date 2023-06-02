from flask import Flask, jsonify, render_template,request,redirect,url_for # For flask implementation
from azure.cosmos import CosmosClient
from flask_caching import Cache
from config import CLOUD_CONFIGURE, PROCESS_CNT
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go # or plotly.express as px
import json
from flask import Flask
import datetime
from datetime import datetime
from datetime import date
from datetime import timedelta
import urllib.request
import plotly.graph_objects as go
from plotly.subplots import make_subplots

app = Flask(__name__)
config = {
    "DEBUG": True,          # some Flask specific configs
    "CACHE_TYPE": "MemcachedCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300
}
app.config.from_mapping(config)
cache = Cache(app)

title = "Stock Price Application with Flask and CosmosDB"
heading = "Stock Price Application with Flask and CosmosDB"
endpoint = CLOUD_CONFIGURE['END_POINT']
key = CLOUD_CONFIGURE['KEY']
client = CosmosClient(endpoint, key)
database_name = 'Final_Project'
database = client.get_database_client(database_name)
container = database.get_container_client(container='stock_version1_5min')

# current_date = date.today().strftime("%Y-%m-%d")
current_date = "2022-05-12"

@app.route("/predict")
def predict(ticker):
	# Request data goes here
	data_list = []
	d = date.today()
	predict_cur_date = d
	ceil_hour = (datetime.now() + (datetime.min - datetime.now()) % timedelta(minutes=30)).hour
	predict_next_date = d + timedelta(days= 7-d.today().weekday() if d.weekday()>3 else 1)
	# d = predict_next_date
	# predict_second_date = d + timedelta(days= 7-d.today().weekday() if d.weekday()>3 else 1)

	for hour in ['09','10','11','12','13','14','15']:
		# if hour > str(ceil_hour): 
		data_obj = {'Time': "{}T{}:30:00.000Z".format(predict_cur_date.strftime("%Y-%m-%d"), hour), "Ticker": ticker}
		data_list.append(data_obj)
	for hour in ['09','10','11','12','13','14','15']:
		data_obj = {'Time': "{}T{}:30:00.000Z".format(predict_next_date.strftime("%Y-%m-%d"), hour), "Ticker": ticker}
		data_list.append(data_obj)

	data = {"Inputs": {"data": data_list}, "GlobalParameters": {"quantiles": [0.025,0.975]}}
	body = str.encode(json.dumps(data))
	api_key = '' # Replace this with the API key for the web service
	url = 'http://fd541b15-8be7-4d6b-8d98-7dec725734de.eastus2.azurecontainer.io/score'
	headers = {'Content-Type':'application/json', 'Authorization':('Bearer '+ api_key)}

	req = urllib.request.Request(url, body, headers)
	try:
		response = urllib.request.urlopen(req)
		res = json.loads(response.read())
		results = res["Results"]['forecast']
		for i in range(len(results)):
			data_list[i]['Close'] = results[i]
		return pd.DataFrame(data_list)

	except urllib.error.HTTPError as error:
		print("The request failed with status code: " + str(error.code))
		# Print the headers - they include the requert ID and the timestamp, which are useful for debugging the failure
		print(error.info())
		print(error.read().decode("utf8", 'ignore'))
	return 

def create_data_frame():
	dflist = []
	for item in list(container.read_all_items(max_item_count=10)):
		item['Price'] = item['val']
		attr_list = item['id'].split('_')
		if len(attr_list) < 3: continue;ç
		item['Ticker'] = attr_list[0]
		item['Indicator'] = attr_list[1]
		item['Time'] = attr_list[2]
		dflist.append(dict(item))
	df = pd.DataFrame(dflist)
	return df

@app.route('/')
@cache.cached(timeout=50)
def index():
	ticker_list = list_all_tickers()
	return render_template('index.html',tickerList = ticker_list, a1="active",t=title,h=heading)

@app.route("/listtickers")
@cache.cached(timeout=50)
def list_all_tickers():
	query = "SELECT * FROM c where c.id like '%_{}%'".format(current_date)
	ticker_list = set()
	for item in list(container.query_items(query=query,enable_cross_partition_query=True)):
		ticker_list.add( item['id'].split('_')[0])
	ticker_list = sorted(ticker_list)
	return ticker_list

def fetch_data(ticker, period):
	if period == "day":
		query = "SELECT * FROM c where c.id like '{}_{}%'".format(ticker, current_date)
		item_list = []
		for item in list(container.query_items(
							query=query,
							enable_cross_partition_query=True
						)):
			item_list.append(dict(item))
		return item_list
	elif period == "week":
		item_list = []
		for i in range(6,-1,-1):
			query_date = (datetime.strptime(current_date, "%Y-%m-%d").date() - timedelta(days=i)).strftime("%Y-%m-%d")
			query = "SELECT * FROM c where c.id like '{}_{}%'".format(ticker, query_date)
			item_list += list(container.query_items(
				query=query,
				enable_cross_partition_query=True
			))
		return item_list

@app.route('/callback/<endpoint>')
def generate_chart(endpoint):
	if endpoint == "predict":
		ticker = request.args.get('data')
		predict_df = predict(ticker)
		predict_df = predict_df.reset_index()
		max = (predict_df['Close'].max())
		min = (predict_df['Close'].min())
		range = max - min
		margin = range * 0.05
		max = max + margin
		min = min - margin
		color = "#d62728" if predict_df['Close'].values[-1] - predict_df['Close'].values[0] >= 0 else "#2ca02c"
		fig = px.area(predict_df, x='Time', y="Close",
			hover_data=("Ticker", "Close", "Time"), 
			color_discrete_sequence=[color],
			range_y=(min,max),
			template="plotly_white" 
		)
		fig.update_xaxes(
			rangebreaks=[
				# NOTE: Below values are bound (not single values), ie. hide x to y
				dict(bounds=["sat", "mon"]),  # hide weekends, eg. hide sat to before mon
				dict(bounds=[16, 9.5], pattern="hour"),  # hide hours outside of 9.30am-4pm
			]
		)
		fig.update_xaxes(showspikes=True)
		fig.update_yaxes(showspikes=True)
		graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
		return graphJSON
	else:
		ticker = request.args.get('data')
		period = request.args.get('period')
		item_list = fetch_data(ticker, period)
		if len(item_list) == 0: 
			return "No Data", 500
		for item in item_list:
			attr_list = item['id'].split('_')
			item['Ticker'] = attr_list[0]
			item['Time'] = attr_list[1]
			item['Open'] = item['val'][0]
			item['Close'] = item['val'][1]
			item['High'] = item['val'][2]
			item['Low'] = item['val'][3]
			item['Volume'] = item['val'][4]

		df = pd.DataFrame(item_list)
		df = df.reset_index()

		if endpoint == "getStock":
			# if period == 'week':
			# 	max = (df['Close'].max())
			# 	min = (df['Close'].min())
			# 	range = max - min
			# 	margin = range * 0.1
			# 	max = max + margin
			# 	min = min - margin
			# 	color = "#d62728" if df['Close'].values[-1] - df['Close'].values[0] >= 0 else "#2ca02c"
			# 	fig = px.area(df, x='Time', y="Close",
			# 		hover_data=("Ticker", "Open","Close","High", "Low", "Volume", "Time"), 
			# 		# title='Close Price Time Series with {}'.format(ticker),
			# 		range_y=(min,max),
			# 		color_discrete_sequence=[color],
			# 		template="plotly_white"
			# 	)
			# 	fig.update_xaxes(
			# 		rangebreaks=[
			# 			# NOTE: Below values are bound (not single values), ie. hide x to y
			# 			dict(bounds=["sat", "mon"]),  # hide weekends, eg. hide sat to before mon
			# 			dict(bounds=[16, 9.5], pattern="hour"),  # hide hours outside of 9.30am-4pm
			# 		]
			# 	)
			# elif period == 'day':
			window = 6 if period == 'day' else 12
			fig = make_subplots(specs=[[{"secondary_y": True}]])
			fig.update_yaxes(showline=True)
			fig.update_layout(template='plotly_white', hovermode='x', margin=dict(b=0, t=30, l=20, r=0))
			fig.update_xaxes(
				rangebreaks=[
					# NOTE: Below values are bound (not single values), ie. hide x to y
					dict(bounds=["sat", "mon"]),  # hide weekends, eg. hide sat to before mon
					dict(bounds=[16, 9.5], pattern="hour"),  # hide hours outside of 9.30am-4pm
				]
			)
			fig.update_xaxes(showspikes=True)
			fig.update_yaxes(showspikes=True)
			fig.add_trace(go.Candlestick(x=df['Time'],
										open=df['Open'],
										high=df['High'],
										low=df['Low'],
										close=df['Close'],
										name='Price',
										increasing_line_color= '#d62728', 
										decreasing_line_color= '#2ca02c',
										showlegend=False
								),
						secondary_y=False,
			)
			fig.add_trace(go.Scatter(x=df['Time'],y=df['Close'].rolling(window=window).mean(),name="MA",marker_color='blue',showlegend=False),
			    secondary_y=False,
			)
			fig.add_trace(go.Bar(
					x=df['Time'], y=df['Volume'], name='Volume', marker={'color':'#67B7DC'},showlegend=False
				),
				secondary_y=True
			)
			fig.update_yaxes(range=[0,df['Volume'].max()*1.1],secondary_y=True)
			fig.update_yaxes(visible=False, secondary_y=True)
			fig.update_layout(xaxis_rangeslider_visible=False)  #hide range slider

			graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
			return graphJSON
		elif endpoint == "getIndicator":
			infoJson = dict()
			infoJson['lastPrice'] = f"{(df['Close'].values[-1]):.2f}"
			infoJson['meanPrice'] = f"{(df['Close'].mean()):.2f}"
			infoJson['meanPrice'] = f"{(df['Close'].mean()):.2f}"
			infoJson['dayLow'] = f"{(df['Close'].min()):.2f}"
			infoJson['dayHigh'] = f"{(df['Close'].max()):.2f}"
			infoJson['meanVol'] = f"{(df['Volume'].mean()):.2f}"
			infoJson['open'] = f"{(df['Open'].mean()):.2f}"
			return infoJson
		else:
			return "Bad endpoint", 400


if __name__ == "__main__":
    app.run(debug=True)
