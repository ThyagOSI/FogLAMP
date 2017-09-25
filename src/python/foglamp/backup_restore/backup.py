#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2017

"""  backup

"""

import time
import sys
import asyncio
import configparser
import os

from foglamp import logger, configuration_manager

import foglamp.backup_restore.lib as lib


_MODULE_NAME = "foglamp_backup"

_MESSAGES_LIST = {

    # Information messages
    "i000001": "Started.",
    "i000002": "Backup completed.",

    # Warning / Error messages
    "e000000": "general error",
    "e000001": "Invalid file name",
    "e000002": "cannot retrieve the configuration from the manager, trying retrieving from file - error details |{0}|",
    "e000003": "cannot retrieve the configuration from file - error details |{0}|",
    "e000004": "cannot delete/purge old backup file on file system - file name |{1}| error details |{0}|",
    "e000005": "cannot delete/purge old backup file on the storage system - file name |{1}| error details |{0}|",
    "e000006": "an error was raised during the backup operation - error details |{0}|",
    "e000007": "Backup failed.",

    "e000010": "cannot start the logger - error details |{0}|",
}
""" Messages used for Information, Warning and Error notice """

_CONFIG_FILE = "configuration.ini"

# Configuration retrieved from the Configuration Manager
_CONFIG_CATEGORY_NAME = 'BACK_REST'
_CONFIG_CATEGORY_DESCRIPTION = 'Configuration of backups and restore'

_CONFIG_DEFAULT = {
    "host": {
        "description": "Host server to backup.",
        "type": "string",
        "default": "localhost"
    },
    "port": {
        "description": "PostgreSQL port.",
        "type": "integer",
        "default": "5432"
    },
    "database": {
        "description": "Database to backup.",
        "type": "string",
        "default": "foglamp"
    },
    "backup_dir": {
        "description": "Directory where the backup will be created.",
        "type": "string",
        "default": "/tmp"
    },
    "retention": {
        "description": "Number of backups to maintain, the old ones will be deleted.",
        "type": "integer",
        "default": "5"
    },
    "timeout": {
        "description": "timeout in seconds for the execution of the commands.",
        "type": "integer",

        # FIXME:
        "default": "20"
        # "default": "1200"
    },

}

_config_from_manager = {}
_config = {}

_logger = ""

_event_loop = ""


class ConfigRetrievalError(RuntimeError):
    """ # FIXME: """
    pass


class BackupError(RuntimeError):
    """ # FIXME: """
    pass


# noinspection PyProtectedMember
def exec_backup(_backup_file):
    """" # FIXME: """

    _logger.debug("{0} - ".format(sys._getframe().f_code.co_name))

    # Executes the backup
    cmd = "pg_dump"
    cmd += " --serializable-deferrable -Fc  "
    cmd += " -h {host} -p {port} {db} > {file}".format(
        host=_config['host'],
        port=_config['port'],
        db=_config['database'],
        file=_backup_file)

    _status, output = lib.exec_wait_retry(cmd, True, timeout=_config['timeout'])

    _logger.debug("{func} - status |{status}| - cmd |{cmd}|  output |{output}| ".format(
                func=sys._getframe().f_code.co_name,
                status=_status,
                cmd=cmd,
                output=output))

    return _status


# noinspection PyProtectedMember
def generate_file_name():
    """" # FIXME: """

    _logger.debug("{0} - ".format(sys._getframe().f_code.co_name))

    # Evaluates the parameters
    execution_time = time.strftime("%Y_%m_%d_%H_%M_%S")

    full_file_name = _config['backup_dir'] + "/" + "foglamp" + "_" + execution_time
    ext = "dump"

    _backup_file = "{file}.{ext}".format(file=full_file_name, ext=ext)

    return _backup_file


def retrieve_configuration_from_manager():
    """" # FIXME: """

    global _config_from_manager
    global _config

    _event_loop.run_until_complete(configuration_manager.create_category(_CONFIG_CATEGORY_NAME,
                                                                         _CONFIG_DEFAULT,
                                                                         _CONFIG_CATEGORY_DESCRIPTION))
    _config_from_manager = _event_loop.run_until_complete(configuration_manager.get_category_all_items
                                                          (_CONFIG_CATEGORY_NAME))

    _config['host'] = _config_from_manager['host']['value']

    _config['port'] = int(_config_from_manager['port']['value'])
    _config['database'] = _config_from_manager['database']['value']
    _config['backup_dir'] = _config_from_manager['backup_dir']['value']
    _config['retention'] = int(_config_from_manager['retention']['value'])
    _config['timeout'] = int(_config_from_manager['timeout']['value'])


def retrieve_configuration_from_file():
    """" # FIXME: """

    global _config

    config_file = configparser.ConfigParser()
    config_file.read(_CONFIG_FILE)

    _config['host'] = config_file['DEFAULT']['host']
    _config['port'] = int(config_file['DEFAULT']['port'])
    _config['database'] = config_file['DEFAULT']['database']
    _config['backup_dir'] = config_file['DEFAULT']['backup_dir']
    _config['retention'] = int(config_file['DEFAULT']['retention'])
    _config['timeout'] = int(config_file['DEFAULT']['timeout'])


def update_configuration_file():
    """" # FIXME: """

    config_file = configparser.ConfigParser()

    config_file['DEFAULT']['host'] = _config['host']
    config_file['DEFAULT']['port'] = str(_config['port'])
    config_file['DEFAULT']['database'] = _config['database']
    config_file['DEFAULT']['backup_dir'] = _config['backup_dir']
    config_file['DEFAULT']['retention'] = str(_config['retention'])
    config_file['DEFAULT']['timeout'] = str(_config['timeout'])

    with open(_CONFIG_FILE, 'w') as file:
        config_file.write(file)


def retrieve_configuration():
    """" # FIXME: """

    try:
        retrieve_configuration_from_manager()

    except Exception as _ex:
        _message = _MESSAGES_LIST["e000002"].format(_ex)
        _logger.warning(_message)

        try:
            retrieve_configuration_from_file()

        except Exception as _ex:
            _message = _MESSAGES_LIST["e000003"].format(_ex)
            _logger.error(_message)

            raise ConfigRetrievalError(ex)
    else:
        update_configuration_file()


def purge_old_backups():
    """" # FIXME: """

    # -1 so at the end of the execution will remain _config['retention'] backups
    backup_to_delete = _config['retention'] - 1

    cmd = """
    
        SELECT  id,file_name FROM foglamp.backups WHERE id NOT in (
            SELECT id FROM foglamp.backups ORDER BY ts DESC LIMIT {0}
        )            
    """.format(backup_to_delete)

    data = lib.storage_retrieve(cmd)

    for row in data:
        file_name = row['file_name']

        if os.path.exists(file_name):
            try:
                os.remove(file_name)

            except Exception as _ex:
                _message = _MESSAGES_LIST["e000004"].format(file_name, _ex)
                _logger.warning(_message)

        try:
            cmd = """
                DELETE FROM foglamp.backups WHERE file_name='{0}'
             """.format(file_name)

            lib.storage_update(cmd)

        except Exception as _ex:
            _message = _MESSAGES_LIST["e000005"].format(file_name, _ex)
            _logger.warning(_message)


def start():
    """  Setup the correct state for the execution of the restore

    Args:
    Returns:
    Raises:
    Todo:
    """

    retrieve_configuration()
    purge_old_backups()


if __name__ == "__main__":

    try:
        _logger = logger.setup(_MODULE_NAME)

        # Set the logger for the library
        lib._logger = _logger

    except Exception as ex:
        message = _MESSAGES_LIST["e000010"].format(str(ex))
        current_time = time.strftime("%Y-%m-%d %H:%M:%S:")

        print("{0} - ERROR - {1}".format(current_time, message))
        sys.exit(1)

    else:

        try:
            _event_loop = asyncio.get_event_loop()

            start()

            backup_file = generate_file_name()

            lib.backup_status_create(backup_file, lib.BACKUP_STATUS_RUNNING)
            status = exec_backup(backup_file)
            lib.backup_status_update(backup_file, status)

            if status == lib.BACKUP_STATUS_SUCCESSFUL:
                _logger.info(_MESSAGES_LIST["i000002"])
                sys.exit(0)

            else:
                _logger.error(_MESSAGES_LIST["e000007"])
                sys.exit(1)

        except Exception as ex:
            message = _MESSAGES_LIST["e000006"].format(ex)

            _logger.exception(message)
            sys.exit(1)
