import psutil
import subprocess
from time import sleep
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json
import configparser
from pathlib import Path, PurePath
from datetime import datetime
import platform
import sys
import os
import traceback
from io import TextIOWrapper
from Exchange import Exchange, Exchanges

SYMBOLMAP = {
    #Binance
    "RONIN": "RON",
    "1000BONK": "BONK",
    "1000FLOKI": "FLOKI",
    "1000LUNC": "LUNC",
    "1000PEPE": "PEPE",
    "1000RATS": "rats",
    "1000SHIB": "SHIB",
    "SHIB1000": "SHIB",
    "1000XEC": "XEC",
    "BEAMX": "BEAM",
    "DODOX": "DODO",
    "LUNA2": "LUNA",
    "NEIROETH": "NEIRO",
    "1MBABYDOGE": "BabyDoge",
    #Bybit
    "1000000BABYDOGE": "BabyDoge",
    "10000000AIDOGE": "AIDOGE",
    "1000000MOG": "MOG",
    "1000000PEIPEI": "PEIPEI",
    "10000COQ": "COQ",
    "10000LADYS": "LADYS",
    "10000SATS": "1000SATS",
    "10000WEN": "WEN",
    "10000WHY": "WHY",
    "1000APU": "APU",
    "1000BEER": "BEER",
    "1000BTT": "BTT",
    "1000CATS": "CATS",
    "1000CAT": "CAT",
    "1000MUMU": "MUMU",
    "1000NEIROCTO": "NEIRO",
    "1000TURBO": "TURBO",
    "DOP1": "DOP",
    "GOMINING": "Gomining",
    "RAYDIUM": "RAY",
    "USDE": "USDe",
    #Bitget
    "OMNI1": "OMNI",
    "VELO1": "VELO",
    #OKX
    "SATS": "1000SATS",
    #Hyperliquid
    "kBONK": "BONK",
    "kFLOKI": "FLOKI",
    "kLUNC": "LUNC",
    "kPEPE": "PEPE",
    "kSHIB": "SHIB",
    "kDOGS": "DOGS",
    #Kucoin
    "10000CAT": "CAT",
    "1000PEPE2": "PEPE2.0",
    "NEIROCTO": "NEIRO",
    "XBT": "BTC",
   }

class CoinData:
    def __init__(self):
        pbgdir = Path.cwd()
        self.piddir = Path(f'{pbgdir}/data/pid')
        if not self.piddir.exists():
            self.piddir.mkdir(parents=True)
        self.pidfile = Path(f'{self.piddir}/pbcoindata.pid')
        self.my_pid = None
        self._api_key = None
        self._fetch_limit = 5000
        self._fetch_interval = 24
        self.load_config()
        self.data = None
        self._exchange = Exchanges.list()[0]
        self.exchanges = Exchanges.list()
        self.exchange_index = self.exchanges.index(self.exchange)
        self._symbols = []
        self._symbols_cpt = []
        self._symbols_data = []
        self.approved_coins = []
        self.ignored_coins = []
        self.load_symbols()
        self._market_cap = 0
        self._vol_mcap = 10.0
    
    @property
    def api_key(self):
        return self._api_key
    @api_key.setter
    def api_key(self, new_api_key):
        self._api_key = new_api_key
    
    @property
    def fetch_limit(self):
        return self._fetch_limit
    @fetch_limit.setter
    def fetch_limit(self, new_fetch_limit):
        self._fetch_limit = new_fetch_limit
    
    @property
    def fetch_interval(self):
        return self._fetch_interval
    @fetch_interval.setter
    def fetch_interval(self, new_fetch_interval):
        self._fetch_interval = new_fetch_interval

    @property
    def exchange(self):
        return self._exchange
    @exchange.setter
    def exchange(self, new_exchange):
        self._exchange = new_exchange
        self.load_symbols()
        self.list_symbols()

    @property
    def symbols(self):
        if not self._symbols:
            self.load_symbols()
        return self._symbols

    @property
    def symbols_cpt(self):
        if not self._symbols_cpt:
            self.load_symbols()
        return self._symbols_cpt

    @property
    def symbols_data(self):
        if not self._symbols_data:
            self.list_symbols()
        return self._symbols_data
    
    @property
    def market_cap(self):
        return self._market_cap
    @market_cap.setter
    def market_cap(self, new_market_cap):
        if self._market_cap != new_market_cap:
            self._market_cap = new_market_cap
            self.list_symbols()
    
    @property
    def vol_mcap(self):
        return self._vol_mcap
    @vol_mcap.setter
    def vol_mcap(self, new_vol_mcap):
        if self._vol_mcap != new_vol_mcap:
            self._vol_mcap = new_vol_mcap
            self.list_symbols()

    def run(self):
        if not self.is_running():
            pbgdir = Path.cwd()
            cmd = [sys.executable, '-u', PurePath(f'{pbgdir}/PBCoinData.py')]
            if platform.system() == "Windows":
                creationflags = subprocess.DETACHED_PROCESS
                creationflags |= subprocess.CREATE_NO_WINDOW
                subprocess.Popen(cmd, stdout=None, stderr=None, cwd=pbgdir, text=True, creationflags=creationflags)
            else:
                subprocess.Popen(cmd, stdout=None, stderr=None, cwd=pbgdir, text=True, start_new_session=True)
            count = 0
            while True:
                if count > 5:
                    print(f'{datetime.now().isoformat(sep=" ", timespec="seconds")} Error: Can not start PBCoinData')
                sleep(1)
                if self.is_running():
                    break
                count += 1

    def stop(self):
        if self.is_running():
            print(f'{datetime.now().isoformat(sep=" ", timespec="seconds")} Stop: PBCoinData')
            psutil.Process(self.my_pid).kill()

    def restart(self):
        if self.is_running():
            self.stop()
            self.run()

    def is_running(self):
        self.load_pid()
        try:
            if self.my_pid and psutil.pid_exists(self.my_pid) and any(sub.lower().endswith("pbcoindata.py") for sub in psutil.Process(self.my_pid).cmdline()):
                return True
        except psutil.NoSuchProcess:
            pass
        return False

    def load_pid(self):
        if self.pidfile.exists():
            with open(self.pidfile) as f:
                pid = f.read()
                self.my_pid = int(pid) if pid.isnumeric() else None

    def save_pid(self):
        self.my_pid = os.getpid()
        with open(self.pidfile, 'w') as f:
            f.write(str(self.my_pid))

    def load_config(self):
        pb_config = configparser.ConfigParser()
        pb_config.read('pbgui.ini')
        if pb_config.has_option("coinmarketcap", "api_key"):
            self._api_key = pb_config.get("coinmarketcap", "api_key")
        if pb_config.has_option("coinmarketcap", "fetch_limit"):
            self._fetch_limit = int(pb_config.get("coinmarketcap", "fetch_limit"))
        if pb_config.has_option("coinmarketcap", "fetch_interval"):
            self._fetch_interval = int(pb_config.get("coinmarketcap", "fetch_interval"))
    
    def save_config(self):
        pb_config = configparser.ConfigParser()
        pb_config.read('pbgui.ini')
        if not pb_config.has_section("coinmarketcap"):
            pb_config.add_section("coinmarketcap")
        pb_config.set("coinmarketcap", "api_key", self.api_key)
        pb_config.set("coinmarketcap", "fetch_limit", str(self.fetch_limit))
        pb_config.set("coinmarketcap", "fetch_interval", str(self.fetch_interval))
        with open('pbgui.ini', 'w') as pbgui_configfile:
            pb_config.write(pbgui_configfile)

    def fetch_data(self):
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
        parameters = {
            'start':'1',
            'limit':self.fetch_limit
        }
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': self.api_key,
        }
        session = Session()
        session.headers.update(headers)
        try:
            response = session.get(url, params=parameters)
            self.data = json.loads(response.text)
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            return e
    
    def save_data(self):
        pbgdir = Path.cwd()
        coin_path = f'{pbgdir}/data/coindata'
        if not Path(coin_path).exists():
            Path(coin_path).mkdir(parents=True)
        with Path(f'{coin_path}/coindata.json').open('w') as f:
            json.dump(self.data, f)
    
    def load_data(self):
        pbgdir = Path.cwd()
        coin_path = f'{pbgdir}/data/coindata'
        if Path(f'{coin_path}/coindata.json').exists():
            data_ts = Path(f'{coin_path}/coindata.json').stat().st_mtime
            now_ts = datetime.now().timestamp()
            if data_ts > now_ts - 3600*self.fetch_interval:
                with Path(f'{coin_path}/coindata.json').open() as f:
                    self.data = json.load(f)
                    return
        self.fetch_data()
        self.save_data()
    
    def is_data_fresh(self):
        pbgdir = Path.cwd()
        coin_path = f'{pbgdir}/data/coindata'
        if Path(f'{coin_path}/coindata.json').exists():
            data_ts = Path(f'{coin_path}/coindata.json').stat().st_mtime
            now_ts = datetime.now().timestamp()
            if data_ts > now_ts - 3600*self.fetch_interval:
                return True
        return
    
    def load_symbols(self):
        pb_config = configparser.ConfigParser()
        pb_config.read('pbgui.ini')
        exchange = "kucoinfutures" if self.exchange == "kucoin" else self.exchange
        if pb_config.has_option("exchanges", f'{exchange}.swap'):
            self._symbols = eval(pb_config.get("exchanges", f'{exchange}.swap'))
        if self.exchange in ["binance", "bybit"]:
            if pb_config.has_option("exchanges", f'{exchange}.cpt'):
                self._symbols_cpt = eval(pb_config.get("exchanges", f'{exchange}.cpt'))
                return
        self._symbols_cpt = self._symbols
    
    def list_symbols(self):
        if not self.data:
            self.load_data()
        if "data" not in self.data:
            return
        self._symbols_data = []
        self.approved_coins = []
        self.ignored_coins = []
        for symbol in self.symbols:
            market_cap = 0
            sym = symbol[0:-4]
            if sym in SYMBOLMAP:
                sym = SYMBOLMAP[sym]
            for id, coin in enumerate(self.data["data"]):
                if coin["symbol"] == sym:
                    if coin["quote"]["USD"]["market_cap"]:
                        coin_data = coin
                        market_cap = coin["quote"]["USD"]["market_cap"]
                        break
                    elif coin["self_reported_market_cap"]:
                        coin_data = coin
                        market_cap = coin["self_reported_market_cap"]
                        break
            if symbol not in self._symbols_data:
                if market_cap > 0:
                    symbol_data = {
                        "id": id,
                        "symbol": symbol,
                        "name": coin_data["name"],
                        "price": coin_data["quote"]["USD"]["price"],
                        "volume_24h": coin_data["quote"]["USD"]["volume_24h"],
                        "market_cap": int(market_cap),
                        "vol/mcap": coin_data["quote"]["USD"]["volume_24h"]/market_cap,
                        "link": f'https://coinmarketcap.com/currencies/{coin_data["slug"]}',
                    }
                else:
                    symbol_data = {
                        "id": 999999,
                        "symbol": symbol,
                        "name": "not found on CoinMarketCap",
                        "price": 0,
                        "volume_24h": 0,
                        "market_cap": 0,
                        "vol/mcap": 0,
                        "link": None,
                    }
                # if self.market_cap != 0 or self.vol_mcap != 10.0:
                if market_cap > self.market_cap*1000000 and symbol_data["vol/mcap"] < self.vol_mcap:
                    self._symbols_data.append(symbol_data)
                    self.approved_coins.append(symbol)
                else:
                    self.ignored_coins.append(symbol)
                # else:
                #     self._symbols_data.append(symbol_data)
                #     self.approved_coins.append(symbol)
        # sort by market cap
        self._symbols_data = sorted(self._symbols_data, key=lambda x: x["market_cap"], reverse=True)

    def filter_by_market_cap(self, symbols: list, mc: int):
        ignored_coins = []
        approved_coins = []
        self.load_data()
        for symbol in symbols:
            sym = symbol[0:-4]
            if sym in SYMBOLMAP:
                sym = SYMBOLMAP[sym]
            for coin in self.data["data"]:
                if coin["symbol"] == sym:
                    if coin["quote"]["USD"]["market_cap"] and coin["quote"]["USD"]["market_cap"] > mc:
                        approved_coins.append(symbol)
                        break
                    elif coin["self_reported_market_cap"] and coin["self_reported_market_cap"] > mc:
                        approved_coins.append(symbol)
                        break
            if symbol not in approved_coins:
                ignored_coins.append(symbol)
        return approved_coins, ignored_coins

def main():
    pbgdir = Path.cwd()
    dest = Path(f'{pbgdir}/data/logs')
    if not dest.exists():
        dest.mkdir(parents=True)
    logfile = Path(f'{str(dest)}/PBCoinData.log')
    sys.stdout = TextIOWrapper(open(logfile,"ab",0), write_through=True)
    sys.stderr = TextIOWrapper(open(logfile,"ab",0), write_through=True)
    print(f'{datetime.now().isoformat(sep=" ", timespec="seconds")} Start: PBCoinData')
    pbcoindata = CoinData()
    if pbcoindata.is_running():
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        print(f'{datetime.now().isoformat(sep=" ", timespec="seconds")} Error: PBCoinData already started')
        exit(1)
    pbcoindata.save_pid()
    while True:
        try:
            if logfile.exists():
                if logfile.stat().st_size >= 10485760:
                    logfile.replace(f'{str(logfile)}.old')
                    sys.stdout = TextIOWrapper(open(logfile,"ab",0), write_through=True)
                    sys.stderr = TextIOWrapper(open(logfile,"ab",0), write_through=True)
            if not pbcoindata.is_data_fresh():
                pbcoindata.load_data()
                if pbcoindata.is_data_fresh():
                    print(f'{datetime.now().isoformat(sep=" ", timespec="seconds")} Fetched CoinMarketCap data')
                else:
                    print(f'{datetime.now().isoformat(sep=" ", timespec="seconds")} Error: Can not fetch CoinMarketCap data')
            sleep(60)
        except Exception as e:
            print(f'Something went wrong, but continue {e}')
            traceback.print_exc()

if __name__ == '__main__':
    main()
