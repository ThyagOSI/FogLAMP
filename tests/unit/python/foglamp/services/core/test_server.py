# -*- coding: utf-8 -*-

# FOGLAMP_BEGIN
# See: http://foglamp.readthedocs.io/
# FOGLAMP_END


import json
from unittest.mock import MagicMock, patch
from aiohttp import web
import pytest

from foglamp.services.common.microservice_management import routes as management_routes
from foglamp.services.core.server import Server
from foglamp.common.web import middleware
from foglamp.services.core.interest_registry.interest_registry import InterestRegistry
from foglamp.services.core.interest_registry.interest_record import InterestRecord
from foglamp.services.core.interest_registry import exceptions as interest_registry_exceptions
from foglamp.services.core.service_registry.service_registry import ServiceRegistry
from foglamp.common.service_record import ServiceRecord
from foglamp.services.core.service_registry import exceptions as service_registry_exceptions
from foglamp.services.core.api import configuration as conf_api
from foglamp.common.storage_client.storage_client import StorageClient
from foglamp.common.configuration_manager import ConfigurationManager
from foglamp.common.audit_logger import AuditLogger


__author__ = "Vaibhav Singhal, Ashish Jabble"
__copyright__ = "Copyright (c) 2017 OSIsoft, LLC"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"


@pytest.allure.feature("unit")
@pytest.allure.story("services", "core", "server")
class TestServer:
    @pytest.fixture
    def client(self, loop, test_client):
        app = web.Application(middlewares=[middleware.error_middleware])
        management_routes.setup(app, Server, True)
        return loop.run_until_complete(test_client(app))

    ############################
    # Configuration Management
    ############################
    """ Tests the calls to configuration manager via core management api
        No negative tests added since these are already covered in 
        foglamp/services/core/api/test_configuration.py
    """
    async def test_get_configuration_categories(self, client):
        async def async_mock():
            return web.json_response({'categories': "test"})

        result = {'categories': "test"}
        with patch.object(conf_api, 'get_categories', return_value=async_mock()) as patch_get_all_categories:
            resp = await client.get('/foglamp/service/category')
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert result == json_response
        assert 1 == patch_get_all_categories.call_count

    async def test_get_configuration_category(self, client):
        async def async_mock():
            return web.json_response("test")

        result = "test"
        with patch.object(conf_api, 'get_category', return_value=async_mock()) as patch_category:
            resp = await client.get('/foglamp/service/category/{}'.format("test_category"))
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert result == json_response
        assert 1 == patch_category.call_count

    async def test_create_configuration_category(self, client):
        async def async_mock():
            return web.json_response({"key": "test_name",
                                      "description": "test_category_desc",
                                      "value": "test_category_info"})

        result = {"key": "test_name", "description": "test_category_desc", "value": "test_category_info"}
        with patch.object(conf_api, 'create_category', return_value=async_mock()) as patch_create_category:
            resp = await client.post('/foglamp/service/category')
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert result == json_response
        assert 1 == patch_create_category.call_count

    async def test_get_configuration_item(self, client):
        async def async_mock():
            return web.json_response("test")

        result = "test"
        with patch.object(conf_api, 'get_category_item', return_value=async_mock()) as patch_category_item:
            resp = await client.get('/foglamp/service/category/{}/{}'.format("test_category", "test_item"))
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert result == json_response
        assert 1 == patch_category_item.call_count

    async def test_update_configuration_item(self, client):
        async def async_mock():
            return web.json_response("test")

        result = "test"
        with patch.object(conf_api, 'set_configuration_item', return_value=async_mock()) as patch_update_category_item:
            resp = await client.put('/foglamp/service/category/{}/{}'.format("test_category", "test_item"))
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert result == json_response
        assert 1 == patch_update_category_item.call_count

    async def test_delete_configuration_item(self, client):
        async def async_mock():
            return web.json_response("ok")

        result = "ok"
        with patch.object(conf_api, 'delete_configuration_item_value', return_value=async_mock()) as patch_del_category_item:
            resp = await client.delete('/foglamp/service/category/{}/{}/value'.format("test_category", "test_item"))
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert result == json_response
        assert 1 == patch_del_category_item.call_count

    ############################
    # Register Interest
    ############################
    async def test_bad_uuid_get_interest(self, client):
        resp = await client.get('/foglamp/interest?microserviceid=X')
        assert 400 == resp.status
        assert 'Invalid microservice id X' == resp.reason

    @pytest.mark.parametrize("params, expected_kwargs", [
        ("", {}),
        ("?category=Y", {'category_name': 'Y'}),
        ("?microserviceid=c6bbf3c8-f43c-4b0f-ac48-f597f510da0b", {'microservice_uuid': 'c6bbf3c8-f43c-4b0f-ac48-f597f510da0b'}),
        ("?category=Y&microserviceid=0c501cd3-c45a-439a-bec6-fc08d13f9699",  {'microservice_uuid': '0c501cd3-c45a-439a-bec6-fc08d13f9699', 'category_name': 'Y'})
    ])
    async def test_get_interest_with_filter(self, client, params, expected_kwargs):
        Server._storage_client = MagicMock(StorageClient)
        Server._configuration_manager = ConfigurationManager(Server._storage_client)
        Server._interest_registry = InterestRegistry(Server._configuration_manager)
        with patch.object(Server._interest_registry, 'get', return_value=[]) as patch_get_interest_reg:
            resp = await client.get('/foglamp/interest{}'.format(params))
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert {'interests': []} == json_response
        args, kwargs = patch_get_interest_reg.call_args
        assert expected_kwargs == kwargs

    @pytest.mark.parametrize("params, expected_kwargs, message", [
        ("", {}, "No interest registered"),
        ("?category=Y", {'category_name': 'Y'}, "No interest registered for category Y"),
        ("?microserviceid=c6bbf3c8-f43c-4b0f-ac48-f597f510da0b",
         {'microservice_uuid': 'c6bbf3c8-f43c-4b0f-ac48-f597f510da0b'}, "No interest registered microservice id c6bbf3c8-f43c-4b0f-ac48-f597f510da0b"),
        ("?category=Y&microserviceid=0c501cd3-c45a-439a-bec6-fc08d13f9699",
         {'microservice_uuid': '0c501cd3-c45a-439a-bec6-fc08d13f9699', 'category_name': 'Y'}, "No interest registered for category Y and microservice id 0c501cd3-c45a-439a-bec6-fc08d13f9699")
    ])
    async def test_get_interest_exception(self, client, params, message, expected_kwargs):
        Server._storage_client = MagicMock(StorageClient)
        Server._configuration_manager = ConfigurationManager(Server._storage_client)
        Server._interest_registry = InterestRegistry(Server._configuration_manager)
        with patch.object(Server._interest_registry, 'get', side_effect=interest_registry_exceptions.DoesNotExist) as patch_get_interest_reg:
            resp = await client.get('/foglamp/interest{}'.format(params))
            assert 404 == resp.status
            assert message == resp.reason
        args, kwargs = patch_get_interest_reg.call_args
        assert expected_kwargs == kwargs

    async def test_get_interest(self, client):
        Server._storage_client = MagicMock(StorageClient)
        Server._configuration_manager = ConfigurationManager(Server._storage_client)
        Server._interest_registry = InterestRegistry(Server._configuration_manager)

        data = []
        category_name = 'test_Cat'
        muuid = '0c501cd3-c45a-439a-bec6-fc08d13f9699'
        reg_id = 'c6bbf3c8-f43c-4b0f-ac48-f597f510da0b'
        record = InterestRecord(reg_id, muuid, category_name)
        data.append(record)

        with patch.object(Server._interest_registry, 'get', return_value=data) as patch_get_interest_reg:
            resp = await client.get('/foglamp/interest')
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert {'interests': [{'category': category_name, 'microserviceId': muuid, 'registrationId': reg_id}]} == json_response
        args, kwargs = patch_get_interest_reg.call_args
        assert {} == kwargs

    async def test_bad_uuid_register_interest(self, client):
        request_data = {"category": "COAP", "service": "X"}
        resp = await client.post('/foglamp/interest', data=json.dumps(request_data))
        assert 400 == resp.status
        assert 'Invalid microservice id X' == resp.reason

    async def test_bad_register_interest(self, client):
        Server._storage_client = MagicMock(StorageClient)
        Server._configuration_manager = ConfigurationManager(Server._storage_client)
        Server._interest_registry = InterestRegistry(Server._configuration_manager)

        request_data = {"category": "COAP", "service": "c6bbf3c8-f43c-4b0f-ac48-f597f510da0b"}
        with patch.object(Server._interest_registry, 'register', return_value=None) as patch_reg_interest_reg:
            resp = await client.post('/foglamp/interest', data=json.dumps(request_data))
            assert 400 == resp.status
            assert 'Interest by microservice_uuid {} for category_name {} could not be registered'.format(request_data['service'], request_data['category']) == resp.reason
        args, kwargs = patch_reg_interest_reg.call_args
        assert (request_data['service'], request_data['category']) == args

    async def test_register_interest_exceptions(self, client):
        Server._storage_client = MagicMock(StorageClient)
        Server._configuration_manager = ConfigurationManager(Server._storage_client)
        Server._interest_registry = InterestRegistry(Server._configuration_manager)

        request_data = {"category": "COAP", "service": "c6bbf3c8-f43c-4b0f-ac48-f597f510da0b"}
        with patch.object(Server._interest_registry, 'register', side_effect=interest_registry_exceptions.ErrorInterestRegistrationAlreadyExists) as patch_reg_interest_reg:
            resp = await client.post('/foglamp/interest', data=json.dumps(request_data))
            assert 400 == resp.status
            assert 'An InterestRecord already exists by microservice_uuid {} for category_name {}'.format(request_data['service'], request_data['category']) == resp.reason
        args, kwargs = patch_reg_interest_reg.call_args
        assert (request_data['service'], request_data['category']) == args

    async def test_register_interest(self, client):
        Server._storage_client = MagicMock(StorageClient)
        Server._configuration_manager = ConfigurationManager(Server._storage_client)
        Server._interest_registry = InterestRegistry(Server._configuration_manager)

        request_data = {"category": "COAP", "service": "c6bbf3c8-f43c-4b0f-ac48-f597f510da0b"}
        reg_id = 'a404852d-d91c-47bd-8860-d4ff81b6e8cb'
        with patch.object(Server._interest_registry, 'register', return_value=reg_id) as patch_reg_interest_reg:
            resp = await client.post('/foglamp/interest', data=json.dumps(request_data))
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert {'id': reg_id, 'message': 'Interest registered successfully'} == json_response
        args, kwargs = patch_reg_interest_reg.call_args
        assert (request_data['service'], request_data['category']) == args

    async def test_bad_uuid_unregister_interest(self, client):
        resp = await client.delete('/foglamp/interest/blah')
        assert 400 == resp.status
        assert 'Invalid registration id blah' == resp.reason

    async def test_unregister_interest_exception(self, client):
        Server._storage_client = MagicMock(StorageClient)
        Server._configuration_manager = ConfigurationManager(Server._storage_client)
        Server._interest_registry = InterestRegistry(Server._configuration_manager)

        reg_id = 'c6bbf3c8-f43c-4b0f-ac48-f597f510da0b'
        with patch.object(Server._interest_registry, 'get', side_effect=interest_registry_exceptions.DoesNotExist) as patch_get_interest_reg:
            resp = await client.delete('/foglamp/interest/{}'.format(reg_id))
            assert 404 == resp.status
            assert 'InterestRecord with registration_id {} does not exist'.format(reg_id) == resp.reason
        args, kwargs = patch_get_interest_reg.call_args
        assert {'registration_id': reg_id} == kwargs

    async def test_unregister_interest(self, client):
        Server._storage_client = MagicMock(StorageClient)
        Server._configuration_manager = ConfigurationManager(Server._storage_client)
        Server._interest_registry = InterestRegistry(Server._configuration_manager)

        data = []
        category_name = 'test_Cat'
        muuid = '0c501cd3-c45a-439a-bec6-fc08d13f9699'
        reg_id = 'c6bbf3c8-f43c-4b0f-ac48-f597f510da0b'
        record = InterestRecord(reg_id, muuid, category_name)
        data.append(record)

        with patch.object(Server._interest_registry, 'get', return_value=data) as patch_get_interest_reg:
            with patch.object(Server._interest_registry, 'unregister', return_value=[]) as patch_unregister_interest:
                resp = await client.delete('/foglamp/interest/{}'.format(reg_id))
                assert 200 == resp.status
                r = await resp.text()
                json_response = json.loads(r)
                assert {'id': reg_id, 'message': 'Interest unregistered'} == json_response
            args, kwargs = patch_unregister_interest.call_args
            assert (reg_id,) == args
        args1, kwargs1 = patch_get_interest_reg.call_args
        assert {'registration_id': reg_id} == kwargs1

    ############################
    # Register Service
    ############################
    @pytest.mark.parametrize("params, obj, expected_kwargs", [
        ("", "all", {}),
        ("?name=Y", "get", {'name': 'Y'}),
        ("?type=Storage", "get", {'s_type': 'Storage'}),
        ("?name=Y&type=Storage", "filter_by_name_and_type", {'name': 'Y', 's_type': 'Storage'})
    ])
    async def test_get_service(self, client, params, obj, expected_kwargs):
        with patch.object(ServiceRegistry, obj, return_value=[]) as patch_get_service_reg:
            resp = await client.get('/foglamp/service{}'.format(params))
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert {'services': []} == json_response
        args, kwargs = patch_get_service_reg.call_args
        assert expected_kwargs == kwargs

    @pytest.mark.parametrize("params, obj, expected_kwargs, message", [
        ("", "all", {}, "No service found"),
        ("?name=Y", "get", {'name': 'Y'}, "Service with name Y does not exist"),
        ("?type=Storage", "get", {'s_type': 'Storage'}, "Service with type Storage does not exist"),
        ("?name=Y&type=Storage", "filter_by_name_and_type", {'name': 'Y', 's_type': 'Storage'}, "Service with name Y and type Storage does not exist")
    ])
    async def test_get_service_exception(self, client, params, obj, expected_kwargs, message):
        with patch.object(ServiceRegistry, obj, side_effect=service_registry_exceptions.DoesNotExist) as patch_service_reg:
            resp = await client.get('/foglamp/service{}'.format(params))
            assert 404 == resp.status
            assert message == resp.reason
        args, kwargs = patch_service_reg.call_args
        assert expected_kwargs == kwargs

    async def test_get_services(self, client):
        sid = "c6bbf3c8-f43c-4b0f-ac48-f597f510da0b"
        sname = "name"
        stype = "Southbound"
        sprotocol = "http"
        saddress = "localhost"
        sport = 1234
        smgtport = 4321
        data = []
        record = ServiceRecord(sid, sname, stype, sprotocol, saddress, sport, smgtport)
        data.append(record)

        with patch.object(ServiceRegistry, 'all', return_value=data) as patch_get_all_service_reg:
            resp = await client.get('/foglamp/service')
            assert 200 == resp.status
            r = await resp.text()
            json_response = json.loads(r)
            assert {'services': [{'id': sid, 'management_port': smgtport, 'address': saddress, 'name': sname, 'type': stype, 'protocol': sprotocol, 'status': 'running', 'service_port': sport}]} == json_response
        args, kwargs = patch_get_all_service_reg.call_args
        assert {} == kwargs

    @pytest.mark.parametrize("request_data, message", [
        ({"type": "Storage", "name": "Storage Services", "address": "127.0.0.1", "service_port": "8090", "management_port": 1090}, "Service's service port can be a positive integer only"),
        ({"type": "Storage", "name": "Storage Services", "address": "127.0.0.1", "service_port": 8090, "management_port": "1090"}, "Service management port can be a positive integer only"),
        ({"type": "Storage", "name": "Storage Services", "address": "127.0.0.1", "service_port": "8090", "management_port": "1090"}, "Service's service port can be a positive integer only")
    ])
    async def test_bad_register_service(self, client, request_data, message):
        resp = await client.post('/foglamp/service', data=json.dumps(request_data))
        assert 400 == resp.status
        assert message == resp.reason

    @pytest.mark.parametrize("exception_name, message", [
        (service_registry_exceptions.AlreadyExistsWithTheSameName, "A Service with the same name already exists"),
        (service_registry_exceptions.AlreadyExistsWithTheSameAddressAndPort, "A Service is already registered on the same address: 127.0.0.1 and service port: 8090"),
        (service_registry_exceptions.AlreadyExistsWithTheSameAddressAndManagementPort, "A Service is already registered on the same address: 127.0.0.1 and management port: 1090")
    ])
    async def test_register_service_exceptions(self, client, exception_name, message):
        request_data = {"type": "Storage", "name": "Storage Services", "address": "127.0.0.1", "service_port": 8090, "management_port": 1090}
        with patch.object(ServiceRegistry, 'register', side_effect=exception_name):
            resp = await client.post('/foglamp/service', data=json.dumps(request_data))
            assert 400 == resp.status
            assert message == resp.reason

    async def test_service_not_registered(self, client):
        request_data = {"type": "Storage", "name": "Storage Services", "address": "127.0.0.1", "service_port": 8090, "management_port": 1090}
        with patch.object(ServiceRegistry, 'register', return_value=None) as patch_register:
            resp = await client.post('/foglamp/service', data=json.dumps(request_data))
            assert 400 == resp.status
            assert 'Service {} could not be registered'.format(request_data['name']) == resp.reason
        args, kwargs = patch_register.call_args
        assert (request_data['name'], request_data['type'], request_data['address'],  request_data['service_port'], request_data['management_port'], 'http') == args

    async def test_register_service(self, client):
        async def async_mock(return_value):
            return return_value

        request_data = {"type": "Storage", "name": "Storage Services", "address": "127.0.0.1", "service_port": 8090, "management_port": 1090}
        with patch.object(ServiceRegistry, 'register', return_value='1') as patch_register:
            with patch.object(AuditLogger, '__init__', return_value=None):
                with patch.object(AuditLogger, 'information', return_value=async_mock(None)) as audit_info_patch:
                    resp = await client.post('/foglamp/service', data=json.dumps(request_data))
                    assert 200 == resp.status
                    r = await resp.text()
                    json_response = json.loads(r)
                    assert {'message': 'Service registered successfully', 'id': '1'} == json_response
                args, kwargs = audit_info_patch.call_args
                assert 'SRVRG' == args[0]
                assert {'name': request_data['name']} == args[1]
        args, kwargs = patch_register.call_args
        assert (request_data['name'], request_data['type'], request_data['address'], request_data['service_port'], request_data['management_port'], 'http') == args

    async def test_service_not_found_when_unregister(self, client):
        with patch.object(ServiceRegistry, 'get', side_effect=service_registry_exceptions.DoesNotExist) as patch_unregister:
            resp = await client.delete('/foglamp/service/blah')
            assert 404 == resp.status
            assert 'Service with blah does not exist' == resp.reason
        args, kwargs = patch_unregister.call_args
        assert {'idx': 'blah'} == kwargs

    async def test_unregister_service(self, client):
        async def async_mock():
            return ""

        service_id = "c6bbf3c8-f43c-4b0f-ac48-f597f510da0b"
        sname = "name"
        stype = "Southbound"
        sprotocol = "http"
        saddress = "localhost"
        sport = 1234
        smgtport = 4321
        data = []
        record = ServiceRecord(service_id, sname, stype, sprotocol, saddress, sport, smgtport)
        data.append(record)
        Server._storage_client = MagicMock(StorageClient)
        with patch.object(ServiceRegistry, 'get', return_value=data) as patch_get_unregister:
            with patch.object(ServiceRegistry, 'unregister') as patch_unregister:
                with patch.object(AuditLogger, '__init__', return_value=None):
                    with patch.object(AuditLogger, 'information', return_value=async_mock()) as audit_info_patch:
                        resp = await client.delete('/foglamp/service/{}'.format(service_id))
                        assert 200 == resp.status
                        r = await resp.text()
                        json_response = json.loads(r)
                        assert {'id': service_id, 'message': 'Service unregistered'} == json_response
                    args, kwargs = audit_info_patch.call_args
                    assert 'SRVUN' == args[0]
                    assert {'name': sname} == args[1]
            args1, kwargs1 = patch_unregister.call_args
            assert (service_id,) == args1
        args2, kwargs2 = patch_get_unregister.call_args
        assert {'idx': service_id} == kwargs2

    ############################
    # Common
    ############################
    async def test_ping(self, client):
        resp = await client.get('/foglamp/service/ping')
        assert 200 == resp.status
        r = await resp.text()
        json_response = json.loads(r)
        assert 'uptime' in json_response
        assert 0.0 < json_response["uptime"]

    # TODO: tricky one
    async def test_shutdown(self, client):
        pass

    async def test_change(self):
        pass
