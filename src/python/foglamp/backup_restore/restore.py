#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2017

"""  backup

"""

# FIXME:
import argparse
import time
import sys
import configparser
import asyncio
import os

from foglamp import logger, configuration_manager
import foglamp.backup_restore.lib as lib


_MODULE_NAME = "foglamp_restore"

_MESSAGES_LIST = {

    # Information messages
    "i000001": "Started.",
    "i000002": "Restore completed.",

    # Warning / Error messages
    "e000000": "general error",
    "e000001": "Invalid file name",
    "e000002": "cannot retrieve the configuration from the manager, trying retrieving from file - error details |{0}|",
    "e000003": "cannot retrieve the configuration from file - error details |{0}|",
    "e000004": "cannot restore the backup, file doesn't exists - file name |{0}|",
    "e000005": "an error was raised during the restore operation - error details |{0}|",
    "e000006": "cannot start FogLAMP after the restore - error details |{0}|",
    "e000007": "cannot restore the backup, restarting FogLAMP - error details |{0}|",
    "e000008": "cannot identify FogLAMP status, the maximum number of retries has been reached - error details |{0}|",

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

# FIXME:
_base_cmd = "bash -c '"
_base_cmd += "source /home/foglamp/Development/FogLAMP/src/python/venv/foglamp/bin/activate;\\"
_base_cmd += "python3 -m foglamp {0}"
_base_cmd += "'"

# base_cmd = "python3 -m foglamp {0}"

STATUS_NOT_DEFINED = 0
STATUS_STOPPED = 1
STATUS_RUNNING = 2


class ConfigRetrievalError(RuntimeError):
    """ # FIXME: """
    pass


class RestoreError(RuntimeError):
    """ # FIXME: """
    pass


class NoBackupAvailableError(RuntimeError):
    """ # FIXME: """
    pass


class InvalidFileNameError(RuntimeError):
    """ # FIXME: """
    pass


class FileNameError(RuntimeError):
    """ # FIXME: """
    pass


class FogLAMPStartError(RuntimeError):
    """ # FIXME: """
    pass


class FogLAMPStopError(RuntimeError):
    """ # FIXME: """
    pass


# noinspection PyProtectedMember
def foglamp_stop():
    """ Stops FogLAMP for the execution of the backup, doing a cold backup

    Args:
    Returns:
    Raises:
        FogLAMPStopError
    Todo:
    """

    _logger.debug("{func}".format(func=sys._getframe().f_code.co_name))

    cmd = _base_cmd.format("stop")

    # Restore the backup
    status, output = lib.exec_wait_retry(cmd, True, timeout=_config['timeout'])

    _logger.debug("{func} - status |{status}| - cmd |{cmd}| - output |{output}|   ".format(
                func=sys._getframe().f_code.co_name,
                status=status,
                cmd=cmd,
                output=output))

    if status == 0:
        if foglamp_status() == STATUS_STOPPED:
            # FIXME:
            cmd = "pkill -9  -f 'python3 -m foglamp.device'"
            status, output = lib.exec_wait(cmd, True, timeout=_config['timeout'])

            _logger.debug("FogLAMP pkill {0} - output |{1}| -  status |{2}|  ".format(
                                                                        sys._getframe().f_code.co_name,
                                                                        output,
                                                                        status))

        else:
            raise FogLAMPStopError(output)
    else:
        raise FogLAMPStopError(output)


# noinspection PyProtectedMember
def foglamp_start():
    """ Starts FogLAMP after the execution of the restore

    Args:
    Returns:
    Raises:
        FogLAMPStartError
    Todo:
    """

    cmd = _base_cmd.format("start")

    status, output = lib.exec_wait_retry(cmd, True, timeout=_config['timeout'])

    _logger.debug("FogLAMP {0} - output |{1}| -  status |{2}|  ".format(sys._getframe().f_code.co_name,
                                                                        output,
                                                                        status))

    if status == 0:
        if foglamp_status() != STATUS_RUNNING:
            raise FogLAMPStartError

    else:
        raise FogLAMPStartError


# noinspection PyProtectedMember
def foglamp_status():
    """ Check the status of FogLAMP

    Args:
    Returns:
        status: {STATUS_NOT_DEFINED|STATUS_STOPPED|STATUS_RUNNING}
    Raises:
        FogLAMPStartError
    Todo:
    """

    status = STATUS_NOT_DEFINED

    num_exec = 1
    max_exec = 20
    same_status = 1
    same_status_ok = 3
    sleep_time = 1

    while (same_status <= same_status_ok) and (num_exec <= max_exec):

        time.sleep(sleep_time)

        try:
            cmd = _base_cmd.format("status")

            cmd_status, output = lib.exec_wait(cmd, True, timeout=_config['timeout'])

            _logger.debug("{0} - output |{1}| \r - status |{2}|  ".format(sys._getframe().f_code.co_name,
                                                                          output,
                                                                          cmd_status))

            num_exec += 1

            if cmd_status == 0:
                new_status = STATUS_RUNNING

            elif cmd_status == 2:
                new_status = STATUS_STOPPED

        except Exception as e:
            _message = e
            raise _message

        else:
            if same_status == 1:
                same_status += 1

            else:
                if new_status == status:
                    same_status += 1

            status = new_status

    if num_exec >= max_exec:
        _message = _MESSAGES_LIST["e000008"]

        _logger.error(_message)
        status = STATUS_NOT_DEFINED

    return status


# noinspection PyProtectedMember
def exec_restore(backup_file):
    """ Executes the restore of the storage layer from a backup

    Args:
    Returns:
    Raises:
        RestoreError
    Todo:
    """

    _logger.debug("{func} - Restore start |{file}|".format(func=sys._getframe().f_code.co_name,
                                                           file=backup_file))

    database = _config['database']
    host = _config['host']
    port = _config['port']

    # Generates the restore command
    cmd = "pg_restore"
    cmd += " --verbose --clean --no-acl --no-owner "
    cmd += " -h {host} -p {port} -d {db} {file}".format(
        host=host,
        port=port,
        db=database,
        file=backup_file,)

    # Restore the backup
    status, output = lib.exec_wait_retry(cmd, True, timeout=_config['timeout'])
    output_short = output.splitlines()[10]

    _logger.debug("{func} - Restore end - status |{status}| - cmd |{cmd}| - output |{output}|".format(
                                func=sys._getframe().f_code.co_name,
                                status=status,
                                cmd=cmd,
                                output=output_short))

    if status != 0:
        raise RestoreError


# noinspection PyProtectedMember
# noinspection PyUnresolvedReferences
def identify_last_backup():
    """ Identifies latest executed backup either successfully executed or already restored

    Args:
    Returns:
    Raises:
        NoBackupAvailableError: No backup either successfully executed or already restored available
        FileNameError: it is possible to identify an unique backup to restore
    Todo:
    """

    _logger.debug("{0} ".format(sys._getframe().f_code.co_name))

    sql_cmd = """
        SELECT file_name FROM foglamp.backups WHERE (ts,id)=
        (SELECT  max(ts),MAX(id) FROM foglamp.backups WHERE status=0 or status=-2);
    """

    data = lib.storage_retrieve(sql_cmd)

    if len(data) == 0:
        raise NoBackupAvailableError

    elif len(data) == 1:
        _file_name = data[0]['file_name']
    else:
        raise FileNameError

    return _file_name


# noinspection PyProtectedMember
def update_backup_status(_file_name, exit_status):
    """ Update the status of the backup in the storage layer as restored

    Args:
    Returns:
    Raises:
    Todo:
    """

    _logger.debug("{0} - file name |{1}| ".format(sys._getframe().f_code.co_name, _file_name))

    sql_cmd = """

        UPDATE foglamp.backups SET  status={status} WHERE file_name='{file}';

        """.format(status=exit_status,
                   file=_file_name, )

    lib.storage_update(sql_cmd)


def handling_input_parameters():
    """ Handles command line parameters

    Args:
    Returns:
    Raises:
        InvalidFileNameError
    Todo:
    """

    parser = argparse.ArgumentParser(prog=_MODULE_NAME)
    parser.description = '%(prog)s -- restore a fogLAMP backup '

    parser.epilog = ' '

    parser.add_argument('-f', '--file_name',
                        required=False,
                        default=0,
                        help='Backup file to restore.')

    namespace = parser.parse_args(sys.argv[1:])

    try:
        _file_name = namespace.file_name if namespace.file_name else None

    except Exception:
        _message = _MESSAGES_LIST["e000001"].format(str(sys.argv))

        _logger.error(_message)
        raise InvalidFileNameError(_message)

    return _file_name


def retrieve_configuration_from_manager():
    """" # FIXME: """

    global _config_from_manager
    global _config

    _logger.debug("{func}".format(func=sys._getframe().f_code.co_name))

    _event_loop.run_until_complete(configuration_manager.create_category(_CONFIG_CATEGORY_NAME,
                                                                         _CONFIG_DEFAULT,
                                                                         _CONFIG_CATEGORY_DESCRIPTION))
    _config_from_manager = _event_loop.run_until_complete(configuration_manager.get_category_all_items
                                                          (_CONFIG_CATEGORY_NAME))

    _config['host'] = _config_from_manager['host']['value']
    _config['port'] = int(_config_from_manager['port']['value'])
    _config['database'] = _config_from_manager['database']['value']
    _config['backup_dir'] = _config_from_manager['backup_dir']['value']
    _config['timeout'] = int(_config_from_manager['timeout']['value'])


def retrieve_configuration_from_file():
    """" # FIXME: """

    global _config

    _logger.debug("{func}".format(func=sys._getframe().f_code.co_name))

    config_file = configparser.ConfigParser()
    config_file.read(_CONFIG_FILE)

    _config['host'] = config_file['DEFAULT']['host']
    _config['port'] = int(config_file['DEFAULT']['port'])
    _config['database'] = config_file['DEFAULT']['database']
    _config['backup_dir'] = config_file['DEFAULT']['backup_dir']
    _config['timeout'] = int(config_file['DEFAULT']['timeout'])


def update_configuration_file():
    """" # FIXME: """

    _logger.debug("{func}".format(func=sys._getframe().f_code.co_name))

    config_file = configparser.ConfigParser()

    config_file['DEFAULT']['host'] = _config['host']
    config_file['DEFAULT']['port'] = str(_config['port'])
    config_file['DEFAULT']['database'] = _config['database']
    config_file['DEFAULT']['backup_dir'] = _config['backup_dir']
    config_file['DEFAULT']['timeout'] = str(_config['timeout'])

    with open(_CONFIG_FILE, 'w') as file:
        config_file.write(file)


def retrieve_configuration():
    """" # FIXME: """

    _logger.debug("{func}".format(func=sys._getframe().f_code.co_name))

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


def start():
    """  Setup the correct state for the execution of the restore

    Args:
    Returns:
    Raises:
    Todo:
    """

    _logger.debug("{func}".format(func=sys._getframe().f_code.co_name))

    retrieve_configuration()


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

            # Checks if a file name is provided as command line parameter, if not it considers latest backup
            file_name = handling_input_parameters()

            if not file_name:
                file_name = identify_last_backup()
            else:
                if not os.path.exists(file_name):
                    message = _MESSAGES_LIST["e000004"].format(file_name)

                    raise FileNotFoundError(message)

            foglamp_stop()

            # Cases :
            # exit 0 - restore=ok, start=ok
            # exit 1 - restore=ok, start=error
            # exit 1 - restore=error, regardless of the start
            try:
                exec_restore(file_name)
                lib.backup_status_update(file_name, lib.BACKUP_STATUS_RESTORED)
                exit_value = 0

            except Exception as ex:
                message = _MESSAGES_LIST["e000007"].format(ex)

                _logger.exception(message)
                exit_value = 1

            finally:
                try:
                    foglamp_start()
                    _logger.info(_MESSAGES_LIST["i000002"])

                except Exception as ex:
                    message = _MESSAGES_LIST["e000006"].format(ex)

                    _logger.exception(message)
                    exit_value = 1

            sys.exit(exit_value)

        except Exception as ex:
            message = _MESSAGES_LIST["e000005"].format(ex)

            _logger.exception(message)
            sys.exit(1)
