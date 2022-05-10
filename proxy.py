import falcon
import json
import os
import types
import urllib.request
import concurrent.futures
import threading
import sys
import time
import logging

class RepositoryCollection(types.SimpleNamespace):
    repositories: []
    
    def __init__(self, /, **kwargs) -> None:
        self.__dict__.update(kwargs)

class ProxyConfig(types.SimpleNamespace):
    registries = {}
    
    def __init__(self, /, **kwargs) -> None:
        self.__dict__.update(kwargs)

class CatalogResource:
    def __init__(self, config) -> None:
        self.__config = config or Config()
        self.__repositories = []
        self.__lck = threading.Lock()
        self.__log = logging.getLogger()

    def on_get(self, req, resp) -> None:
        n = int(req.params["n"]) if "n" in req.params.keys() else 0
        b = req.params["b"] if "b" in req.params.keys() else None
        repositories = self.__filter(n, b)
        try:
            self.__lck.acquire()
            resp.media = { "repositories": repositories }
        finally:
            self.__lck.release()
            
    def __filter(self, number, begin):
        result = self.__repositories[:]
        
        if begin is None:
            if len(result) > 0:
                begin = result[0]
            else:
                return result
        
        if 0 > number or number >= len(result) or not begin in result:
            return []
        
        index = result.index(begin)
        slc = slice(index, min(len(result), index + number))
        if number == 0:
            slc = slice(index, len(result)) 
        
        result = result[slc]
            
        return result
        
    def async_handle_fetch(self) -> threading.Thread:
        t = threading.Thread(target=self.__get_repositories, daemon=True)
        return t
    
    def __fetch(self, prefix, url):
        try:
            self.__log.info("Fetching repository %s as %s", url, prefix)
            with urllib.request.urlopen(f"{url}/v2/_catalog") as response:
                response_content = response.read()
                response_encoding = response.info().get_content_charset('utf-8')
                document = response_content.decode(response_encoding)
                json_content = json.loads(document)
                collection = RepositoryCollection(**json_content)
                return [ f"{prefix}/{f}" for f in collection.repositories ]
        except Exception as e:
            self.__log.exception(e)
        
        return []
    
    def __get_repositories(self) -> None:
        while (True):
            self.__log.info("Fetching repositories ...")
            futures = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                for registry_name, registry_url in self.__config.registries.items():
                    ft = executor.submit(self.__fetch, registry_name, registry_url)
                    futures.append(ft)
            
            dnd = concurrent.futures.wait(futures)
            done = dnd.done
            reps = []
            for item in done:
                reps.extend(item.result())
            
            self.__log.info("Finished fetching repositories ...")
            
            try:
                self.__lck.acquire()
                self.__repositories = reps[:]
            finally:
                self.__lck.release()
            
            self.__log.info("Waiting for next turn.")
            time.sleep(30.0)
        

cfg = os.getenv("PROXY_CONFIG_FILE") or "/etc/proxy/proxy.json"
if not os.path.isfile(cfg):
    raise FileNotFoundError(cfg)

config = { "registries": [] }
with open(cfg) as fp:
    config = json.load(fp)

config_instance = ProxyConfig(**config)

app = falcon.App()
res = CatalogResource(config_instance)
app.add_route("/", res)
res.async_handle_fetch().start()

