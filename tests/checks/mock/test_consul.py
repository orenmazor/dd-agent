import random
from checks import AgentCheck
from tests.checks.common import AgentCheckTest

MOCK_CONFIG = {
    'init_config': {},
    'instances' : [{
        'url': 'http://localhost:8500',
        'perform_catalog_checks': True
    }]
}


class TestCheckConsul(AgentCheckTest):
    CHECK_NAME = 'consul'

    def mock_get_services_in_cluster(self, instance):
        return {
            "service-1": [
                "az-us-east-1a"
            ],
            "service-2": [
                "az-us-east-1a"
            ],
            "service-3": [
                "az-us-east-1a"
            ],
            "service-4": [
                "az-us-east-1a"
            ],
            "service-5": [
                "az-us-east-1a"
            ],
            "service-6": [
                "az-us-east-1a"
            ]
        }

    def mock_get_nodes_in_cluster(self, instance):
        return [
            {
                "Address": "10.0.2.15",
                "Node": "node-1"
            },
            {
                "Address": "10.0.2.25",
                "Node": "node-2"
            },
            {
                "Address": "10.0.2.35",
                "Node": "node-2"
            },
        ]


    def mock_get_nodes_with_service(self, instance, service):
        def _get_random_ip():
            rand_int = int(15 * random.random()) + 10
            return "10.0.2.{0}".format(rand_int)

        return [
            {
                "Address": _get_random_ip(),
                "Node": "dogbox-aadityatalwai",
                "ServiceAddress": "",
                "ServiceID": service,
                "ServiceName": service,
                "ServicePort": 80,
                "ServiceTags": [
                    "az-us-east-1a"
                ]
            }
        ]

    def mock_get_datacenter(self, instance):
        return 'dc1'

    def mock_should_check(self, instance):
        return True

    def _get_consul_mocks(self):
        return {
            'get_services_in_cluster': self.mock_get_services_in_cluster,
            'get_nodes_in_cluster': self.mock_get_nodes_in_cluster,
            'get_nodes_with_service': self.mock_get_nodes_with_service,
            'should_check': self.mock_should_check,
            '_get_agent_datacenter': self.mock_get_datacenter
        }

    def test_get_nodes_in_cluster(self):
        self.run_check(MOCK_CONFIG, mocks=self._get_consul_mocks())
        self.assertMetric('consul.catalog.nodes_up', value=3, tags=['consul_datacenter:dc1'])

    def test_get_services_in_cluster(self):
        self.run_check(MOCK_CONFIG, mocks=self._get_consul_mocks())
        self.assertMetric('consul.catalog.services_up', value=6, tags=['consul_datacenter:dc1'])

    def test_get_nodes_with_service(self):
        self.run_check(MOCK_CONFIG, mocks=self._get_consul_mocks())
        self.assertMetric('consul.catalog.nodes_up', value=1, tags=['consul_service_id:service-1'])

    def test_get_services_on_node(self):
        self.run_check(MOCK_CONFIG, mocks=self._get_consul_mocks())
        self.assertMetric('consul.catalog.services_up', value=6, tags=['consul_node_id:dogbox-aadityatalwai'])

    def test_new_leader_event(self):
        pass
