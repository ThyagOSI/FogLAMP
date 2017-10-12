# -*- coding: utf-8 -*-

# FOGLAMP_BEGIN
# See: http://foglamp.readthedocs.io/
# FOGLAMP_END

"""Core server module"""

import os
import signal
import asyncio
from aiohttp import web
import subprocess

from foglamp import logger
from foglamp.core import routes
from foglamp.core import middleware
from foglamp.core.scheduler import Scheduler
from foglamp.core.http_server import MultiApp
from foglamp.core.service_registry.instance import Service

__author__ = "Praveen Garg, Terris Linenbach"
__copyright__ = "Copyright (c) 2017 OSIsoft, LLC"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"

_logger = logger.setup(__name__)

# TODO: FIXME: the ROOT directory
_FOGLAMP_ROOT = '/home/foglamp/foglamp/FogLAMP'
_STORAGE_DIR = os.path.expanduser(_FOGLAMP_ROOT + '/services/storage')
_STORAGE_DIR = r"/home/foglamp/Downloads/store/1010"

class Server:
    """FOGLamp core server. Starts the FogLAMP scheduler and the FogLAMP REST server."""

    """Class attributes"""
    scheduler = None
    """ foglamp.core.Scheduler """

    @staticmethod
    def _make_app():
        """Creates the REST server

        :rtype: web.Application
        """
        app = web.Application(middlewares=[middleware.error_middleware])
        routes.setup(app)
        return app

    @staticmethod
    def _make_core_app():
        """Creates the Service management REST server Core a.k.s service registry

        :rtype: web.Application
        """
        app = web.Application(middlewares=[middleware.error_middleware])
        routes.core_setup(app)
        return app

    @classmethod
    async def _start_scheduler(cls):
        """Starts the scheduler"""
        cls.scheduler = Scheduler()
        await cls.scheduler.start()

    @classmethod
    def _start_storage(cls, host, m_port):
        try:
            cmd_with_args = ['./storage', '--address={}'.format(host),
                             '--port={}'.format(m_port)]
            subprocess.call(cmd_with_args, cwd=_STORAGE_DIR)
        except Exception as ex:
            _logger.exception(str(ex))

    @classmethod
    def _start_core(cls, host, management_port):
        # https://aiohttp.readthedocs.io/en/stable/_modules/aiohttp/web.html#run_app
        # web.run_app(cls._make_core_app(), host='0.0.0.0', port=8082)

        ma = MultiApp()
        ma.configure_app(cls._make_core_app(), host=host, port=management_port)

        # TODO: fetch from app info
        # to register to core; as there is no update mechanism so just register once
        # with service port
        service_port = cls.request_available_port()
        # port = 0 works here!
        ma.configure_app(cls._make_app(), host=host, port=service_port)
        # TODO: allow config / env var to set protocol
        cls._register_core(host, management_port, service_port)
        ma.run_all()

    @classmethod
    def _register_core(cls, host, mgt_port, service_port):
        core_service_id = Service.Instances.register(name="FogLAMP Core", s_type="Core", address=host,
                                                     port=service_port, management_port=mgt_port)

        return core_service_id

    # TODO: remove me | NOT NEEDED (hopefully, we shall be able to get info back from aiohttp)
    @classmethod
    def request_available_port(cls, host='localhost'):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, 0))
        addr, port = s.getsockname()
        s.close()
        return port

    @classmethod
    def start(cls):
        """Starts the server"""

        loop = asyncio.get_event_loop()

        # Register signal handlers
        # Registering SIGTERM creates an error at shutdown. See
        # https://github.com/python/asyncio/issues/396
        for signal_name in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                signal_name,
                lambda: asyncio.ensure_future(cls._stop(loop)))

        # TODO: make management port dynamic?!
        host_address = "localhost"  # fix?!
        core_mgt_port = 8082

        # storage can not use the same port as core api will for mgt port
        cls._start_storage(host_address, core_mgt_port)
        #
        # Fix the order! it works because storage start and registration takes time

        # start scheduler
        # The scheduler must start first because the REST API interacts with it
        loop.run_until_complete(asyncio.ensure_future(cls._start_scheduler()))

        cls._start_core(host=host_address, management_port=core_mgt_port)

        #
        # see http://0.0.0.0:8082/foglamp/service for registered services

    @classmethod
    async def _stop_storage(cls):
        # TODO: make client call to service mgt API to ask to shutdown storage

        pass

    @classmethod
    async def _stop_core(cls):
        # shut down aiohttp apps
        pass

    @classmethod
    async def _stop(cls, loop):
        """Attempts to stop the server

        If the scheduler stops successfully, the event loop is
        stopped.
        """
        if cls.scheduler:
            try:
                await cls.scheduler.stop()
                cls.scheduler = None
            except TimeoutError:
                _logger.exception('Unable to stop the scheduler')
                return

        # Cancel asyncio tasks
        for task in asyncio.Task.all_tasks():
            task.cancel()

        # ^^ should be moved to _stop_scheduler?

        await cls._stop_storage()
        await cls._stop_core()

        # stop aiohttp (shutdown apps) before loop? _stop_core()
        loop.stop()
