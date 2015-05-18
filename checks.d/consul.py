# 3p
import requests

# stdlib
from datetime import datetime

# project
from checks import AgentCheck


class ConsulCheck(AgentCheck):
    CONSUL_CHECK = 'consul.up'
    HEALTH_CHECK = 'consul.check'

    CONSUL_CATALOG_CHECK = 'consul.catalog'
    CONSUL_NODE_CHECK = 'consul.node'

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)

        self._last_known_leader = None
        self._instance_to_config = {}


    def consul_request(self, instance, endpoint):
        url = "{}{}".format(instance.get('url'), endpoint)
        try:
            resp = requests.get(url)
        except requests.exceptions.Timeout:
            self.log.exception('Consul request to {0} timed out'.format(url))
            raise

        resp.raise_for_status()
        return resp.json()

    def _check_for_leader_change(self, leader, instance=None):
        agent_dc = self._get_agent_datacenter(instance)

        if leader != self._last_known_leader and self._last_known_leader is not None:
            self.event({
                "timestamp": datetime.utcnow(),
                "event_type": "consul.new_leader",
                "api_key": self.agentConfig.get("api_key", ''),
                "msg_title": "New Consul Leader Elected in {0}".format(agent_dc),
                "aggregation_key": "consul.new_leader",
                "msg_text": "The Node at {0} is the new leader of the consul cluster {1}".format(
                    leader,
                    agent_dc
                ),
                "tags": ["prev_consul_leader:{0}".format(self._last_known_leader),
                         "curr_consul_leader:{0}".format(leader)]
            })

        self._last_known_leader = leader

    def _is_self_leader(self, instance):
        leader = self.consul_request(instance, '/v1/status/leader')
        return agent_url == leader

    def _get_agent_url(self, instance):
        instance_url = instance.get('url')

        local_config = self._instance_to_config.get('instance_url',
                                                    self.consul_request(instance, '/v1/agent/self'))
        if instance_url not in self._instance_to_config:
            self._instance_to_config[instance_url] = local_config

        agent_addr = local_config.get('Config', {}).get('AdvertiseAddr')
        agent_port = local_config.get('Config', {}).get('Ports', {}).get('Server')
        agent_url = "{}:{}".format(agent_addr, agent_port)
        return agent_url

    def _get_agent_datacenter(self, instance):
        local_config = self._instance_to_config.get('instance_url',
                                                    self.consul_request(instance, '/v1/agent/self'))
        if instance_url not in self._instance_to_config:
            self._instance_to_config[instance_url] = local_config
        agent_dc = local_config.get('Config', {}).get('Datacenter')
        return agent_dc

    def should_check(self, instance):
        try:
            agent_url = self._get_agent_url(instance)
            leader = self.consul_request(instance, '/v1/status/leader')
            self._check_for_leader_change(leader)
            return agent_url == leader

        except Exception as e:
            return False

    def get_services_in_cluster(self, instance):
        return self.consul_request(instance, '/v1/catalog/services')

    def get_nodes_in_cluster(self, instance):
        return self.consul_request(instance, '/v1/catalog/nodes')

    def get_nodes_with_service(self, instance, service, tag=None):
        if tag:
            consul_request_url = '/v1/catalog/service/{0}?tag={1}'.format(service,tag)
        else:
            consul_request_url = '/v1/catalog/service/{0}'.format(service)

        return self.consul_request(instance, consul_request_url)

    def get_services_on_node(self, instance, node):
        return self.consul_request(instance, '/v1/catalog/node/{0}'.format(node))

    def check(self, instance):
        if not self.should_check(instance):
            self.log.debug("Skipping check for this instance")
            return

        service_whitelist = instance.get('service_whitelist',
                                         self.init_config.get('service_whitelist', []))

        service_check_tags = ['consul_url:{0}'.format(instance.get('url'))]
        perform_catalog_checks = instance.get('perform_catalog_checks',
                                              self.init_config.get('perform_catalog_checks'))

        try:
            health_state = self.consul_request(instance, '/v1/health/state/any')

            STATUS_SC = {
                'passing': AgentCheck.OK,
                'warning': AgentCheck.WARNING,
                'critical': AgentCheck.CRITICAL,
            }

            for check in health_state:
                status = STATUS_SC.get(check['Status'])
                if status is None:
                    continue

                tags = ["check:{}".format(check["CheckID"])]
                if check["ServiceName"]:
                    tags.append("service:{}".format(check["ServiceName"]))
                if check["ServiceID"]:
                    tags.append("service-id:{}".format(check["ServiceID"]))

            services = self.get_services_in_cluster(instance)
            self.service_check(self.HEALTH_CHECK, status, tags=tags)

        except Exception as e:
            self.service_check(self.CONSUL_CHECK, AgentCheck.CRITICAL,
                               tags=service_check_tags)
        else:
            self.service_check(self.CONSUL_CHECK, AgentCheck.OK,
                               tags=service_check_tags)

        if perform_catalog_checks:
            services = self.get_services_in_cluster(instance) #TODO: Service whitelist here!!
            nodes = self.get_nodes_in_cluster(instance)

            main_tags = []
            agent_dc = self._get_agent_datacenter(instance)
            if agent_dc is not None:
                main_tags.append('consul_datacenter:{0}'.format(agent_dc))

            nodes_to_services = {}

            self.gauge('consul.catalog.services_up', len(services), tags=main_tags)
            self.gauge('consul.catalog.nodes_up', len(nodes), tags=main_tags)

            for service in services:
                nodes_with_service = self.get_nodes_with_service(instance, service)
                node_tags = ['consul_service_id:{0}'.format(service)]

                self.gauge('consul.catalog.nodes_up',
                           len(nodes_with_service),
                           tags=node_tags)

                for n in nodes_with_service:
                    node_id = n.get('Node') or None

                    if not node_id:
                        continue

                    if node_id in nodes_to_services:
                        nodes_to_services[node_id].append(service)
                    else:
                        nodes_to_services[node_id] = [service]

            for node, services in nodes_to_services.items():
                tags = ['consul_node_id:{0}'.format(node)]
                self.gauge('consul.catalog.services_up',
                           len(services),
                           tags=tags)
