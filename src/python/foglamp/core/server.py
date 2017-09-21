# -*- coding: utf-8 -*-

# FOGLAMP_BEGIN
# See: http://foglamp.readthedocs.io/
# FOGLAMP_END

"""Core server module"""
import os
import signal
import asyncio

import sys
from aiohttp import web

from foglamp import logger
from foglamp.core import routes
from foglamp.core import routes_core
from foglamp.core import middleware
from foglamp.core.scheduler import Scheduler

__author__ = "Praveen Garg, Terris Linenbach"
__copyright__ = "Copyright (c) 2017 OSIsoft, LLC"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"

_LOGGER = logger.setup(__name__)  # logging.Logger


class Server:
    """Core server"""

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

    @classmethod
    async def _start_scheduler(cls):
        """Starts the scheduler"""
        cls.scheduler = Scheduler()
        await cls.scheduler.start()

    @classmethod
    def _start(cls):
        """Starts the server"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.ensure_future(cls._start_scheduler()))

        # Register signal handlers
        # Registering SIGTERM creates an error at shutdown. See
        # https://github.com/python/asyncio/issues/396
        for signal_name in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                signal_name,
                lambda: asyncio.ensure_future(cls._stop(loop)))

        # https://aiohttp.readthedocs.io/en/stable/_modules/aiohttp/web.html#run_app
        web.run_app(cls._make_app(), host='0.0.0.0', port=8082)

    @staticmethod
    def _make_core():
        """Creates the REST server

        :rtype: web.Application
        """
        core = web.Application(middlewares=[middleware.error_middleware])
        routes_core.setup(core)
        return core

    @classmethod
    def _run_management_api(cls):
        web.run_app(cls._make_core(), host='0.0.0.0', port=8083)

    @classmethod
    def start(cls):
        try:
            from multiprocessing import Process
            # TODO: Investigate why name is not changing
            m = Process(target=cls._run_management_api, name='management')
            m.start()

            from foglamp.core.storage_server.storage import Storage
            # TODO: Investigate why name is not changing
            s = Process(target=Storage.start, name='storage')
            s.start()

            cls._start()
        except Exception as e:
            sys.stderr.write(format(str(e)) + "\n");
            sys.exit(1)

    @classmethod
    async def _stop(cls, loop):
        """Attempts to stop the server

        If the scheduler stops successfully, the event loop is
        stopped.

        Raises TimeoutError:
            A task is still running. Wait and try again.
        """
        if cls.scheduler:
            try:
                await cls.scheduler.stop()
                cls.scheduler = None
            except TimeoutError:
                _LOGGER.exception('Unable to stop the scheduler')

        # Cancel asyncio tasks
        for task in asyncio.Task.all_tasks():
            task.cancel()

        loop.stop()
