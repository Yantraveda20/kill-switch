import os
import pandas as pd
from NorenRestApiPy.NorenApi import NorenApi
import time
import math
import pyotp

factor2 = pyotp.TOTP(os.getenv("TOTP_SECRET")).now()
user = os.getenv("USER_ID")
pwd = os.getenv("PASSWORD")
vc = os.getenv("VENDOR_CODE")
imei = os.getenv("IMEI")
app_key = os.getenv("APP_KEY")

class ShoonyaApiPy(NorenApi):
    def __init__(self):
        NorenApi.__init__(self, host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')
api = ShoonyaApiPy()

while True:
    try:
        factor2 = pyotp.TOTP(os.getenv("TOTP_SECRET")).now()
        ret = api.login(userid=user, password=pwd, twoFA=factor2, vendor_code=vc, api_secret=app_key, imei=imei)
        if ret['stat'] == 'Ok':
            print('login successful')
            break
    except Exception:
        print('could not login, retrying')
        time.sleep(2)
        continue

max_risk = 150
take_profit = 10

def get_daily_mtm():
    while True:
        try:
            ret = api.get_positions()
            break
        except Exception:
            print('Error Fetching MTM')
            time.sleep(1)
            continue
    mtm = 0
    pnl = 0
    day_m2m = ''
    try:
        for i in ret:
            mtm += float(i['urmtom'])
            pnl += float(i['rpnl'])
            day_m2m = round(mtm + pnl, 2)
    except TypeError:
        print('no open positions for the day, waiting for 1 minute before checking again')
        time.sleep(60)
    return day_m2m

def uni_exit():
    while True:
        try:
            a = api.get_positions()
            a = pd.DataFrame(a)
            ob = api.get_order_book()
            ob = pd.DataFrame(ob)
            break
        except Exception:
            print('uni_exit error fetching positions/orders')
            time.sleep(1)
            continue

    for i in a.itertuples():
        if int(i.netqty) < 0:
            api.place_order(buy_or_sell='B', product_type=i.prd, exchange=i.exch, tradingsymbol=i.tsym, quantity=abs(int(i.netqty)), discloseqty=0, price_type='MKT', price=0, trigger_price=None, retention='DAY', remarks='killswitch_buy')
        if int(i.netqty) > 0:
            api.place_order(buy_or_sell='S', product_type=i.prd, exchange=i.exch, tradingsymbol=i.tsym, quantity=int(i.netqty), discloseqty=0, price_type='MKT', price=0, trigger_price=None, retention='DAY', remarks='killswitch_sell')

    for i in ob.itertuples():
        if i.status == 'TRIGGER_PENDING':
            ret = api.cancel_order(i.norenordno)
        if i.status == 'OPEN':
            ret = api.cancel_order(i.norenordno)

while True:
    mtm = get_daily_mtm()
    try:
        sl_breached = mtm <= (-max_risk)
        profit_done = mtm >= take_profit
    except TypeError:
        pass
    try:
        if sl_breached or profit_done:
            print('Exiting positions and cancelling all standing orders')
            uni_exit()
            if sl_breached:
                sl_breached = False
                max_risk = max_risk + 2
            else:
                profit_done = False
                max_risk = (-take_profit)
                take_profit = take_profit
                print(f"My next MTM SL is {max_risk} and Target is {take_profit}")
    except NameError:
        pass
    time.sleep(0.5)
