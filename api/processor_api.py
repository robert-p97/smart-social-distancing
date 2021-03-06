import time
from threading import Thread
from queue import Queue
from multiprocessing.managers import BaseManager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import uvicorn
import os
import logging
from typing import Dict
from pydantic import BaseModel
from typing import Optional
from api.config_keys import Config,APP,DETECTOR,POSTPROCESSOR,LOGGER,API_
from share.commands import Commands

logger = logging.getLogger(__name__)

class QueueManager(BaseManager): pass

class ProcessorAPI:
    """
    The Webgui object implements a fastapi application and acts as an interface for users.
    Once it is created it will act as a central application for viewing outputs.

    :param config: Is a ConfigEngine instance which provides necessary parameters.
    :param engine_instance:  A ConfigEngine object which store all of the config parameters. Access to any parameter
        is possible by calling get_section_dict method.
    """

    def __init__(self, config):
        self.config = config
        self._setup_queues()
        self._host = self.config.get_section_dict("API")["Host"]
        self._port = int(self.config.get_section_dict("API")["Port"])
        self.app = self.create_fastapi_app()

    def _setup_queues(self):
        QueueManager.register('get_cmd_queue')
        QueueManager.register('get_result_queue')
        self._queue_host = self.config.get_section_dict("CORE")["Host"]
        self._queue_port = int(self.config.get_section_dict("CORE")["QueuePort"])
        auth_key = self.config.get_section_dict("CORE")["QueueAuthKey"]
        self._queue_manager = QueueManager(address=(self._queue_host, self._queue_port), authkey=auth_key.encode('ascii'))
        
        while True:
            try:
                self._queue_manager.connect()
                break
            except ConnectionRefusedError:
                logger.warning("Waiting for core's queue to initiate ... ")
                time.sleep(1)

        logger.info("Connection established to Core's queue")
        self._cmd_queue = self._queue_manager.get_cmd_queue()
        self._result_queue = self._queue_manager.get_result_queue()

    def create_fastapi_app(self):
        # Create and return a fastapi instance
        app = FastAPI()

        if os.environ.get('DEV_ALLOW_ALL_ORIGINS', False):
            # This option allows React development server (which is served on another port, like 3000) to proxy requests
            # to this server.
            # WARNING: read this before enabling it in your environment:
            # https://medium.com/@stestagg/stealing-secrets-from-developers-using-websockets-254f98d577a0
            from fastapi.middleware.cors import CORSMiddleware
            app.add_middleware(CORSMiddleware, allow_origins='*', allow_credentials=True, allow_methods=['*'],
                               allow_headers=['*'])
        app.mount("/static", StaticFiles(directory="/repo/data/web_gui/static"), name="static")

        @app.get("/process-video-cfg")
        async def process_video_cfg():
            logger.info("process-video-cfg requests on api")
            self._cmd_queue.put(Commands.PROCESS_VIDEO_CFG)
            logger.info("waiting for core's response...")
            result = self._result_queue.get()
            return result
        
        @app.get("/stop-process-video")
        async def stop_process_video():
            logger.info("stop-process-video requests on api")
            self._cmd_queue.put(Commands.STOP_PROCESS_VIDEO)
            logger.info("waiting for core's response...")
            result = self._result_queue.get()
            return result
        
        @app.get("/get-config")
        async def get_config():
            logger.info("get-config requests on api")
            sections = self.config.get_sections() 
            result = {}
            for section in sections:
                result[section] = self.config.get_section_dict(section)
            return result
     
        @app.post("/set-config")
        async def create_item(config: Config):
            logger.info("set-config requests on api")
            for key in config:
                if key[1] is not None:
                    for option in key[1]:
                       if option[1] is not None:
                           section = self.config.get_section_dict(key[0])
                           if option[0] in section:
                               if str(section[option[0]]) != str(option[1]):
                                   self.config.set_option_in_section(key[0], option[0], option[1])
                                   logger.warning("config %s is set, stop/start processing is required" %(option[0]))
                                   self.config.reload()
                           else:
                               print("%s is not in %s section of config file" %(option[0],key[0]))
            return config

        return app

    def start(self):
        uvicorn.run(self.app, host=self._host, port=self._port, log_level='info', access_log=False)

