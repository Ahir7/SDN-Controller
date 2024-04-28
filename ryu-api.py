"""
This Ryu application is my own version of the original Ryu ofctl_rest application
that came with this framework. I want to be able to make my own custom APIs that
can allow me to programmatically add flows to OpenFlow devices on a network to better
forward packets to where they need to go. APIs are the future of network programmability
and this is a great way of doing so. I will be taking my time to develop this and testing
it out to see if it works. This will only be using OpenFlow versions 1.3 for compatibility
purposes with the Open vSwitch.
"""
# Importing some modules that were used in the original ofctl_rest application.
import logging
import json
import ast

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller import dpset
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.exception import RyuException
from ryu.ofproto import ofproto_v1_3
from ryu.lib import ofctl_v1_3
from ryu.app.wsgi import ControllerBase
from ryu.app.wsgi import Response
from ryu.app.wsgi import WSGIApplication

the_log = logging.getLogger('Ryu API')  # used to log any issues with the application

supported_of_versions = {
    ofproto_v1_3.OFP_VERSION: ofctl_v1_3
}


# Handle errors for commands and ports, like done in ofctl_rest

class NotValidCommand(RyuException):
    report = "Command invalid: %(command)s"


class NonExistentPort(RyuException):
    report = "No info about port: %(port_number)s"


# Make two wrapper functions, one for handling switch data and other for parsing flow data from json
def device_data(method):
    # Decorator function that runs the functions mapped to the API URIs
    def wrapper(self, req, dpid, *args, **kwargs):
        # try to get the datapath instance from the DPset (which holds all the datapath instances of the switches)
        try:
            dpath = self.dpset.get(int(str(dpid), 0))
        except ValueError:
            the_log.exception(f"DPID invalid: {dpid}")
            return Response(status=400)  # this is if the app gets an invalid datapath ID
        if dpath is None:
            the_log.error(f"Datapath {dpid} does not exist!")
            return Response(status=404)  # This is if the user enters a DPID that does not exist

        # Get the OpenFlow/ofctl version
        try:
            of_version = supported_of_versions.get(dpath.ofproto.OFP_VERSION)
        except KeyError:
            the_log.exception(f"Openflow version not supported: {dpath.ofproto.OFP_VERSION}")
            return Response(status=501)

        # Get the InfoController (class is below)
        try:
            result = method(self, req, dpath, of_version, *args, **kwargs)
            print(of_version, type(of_version))
            body = json.dumps(result)
            return Response(content_type='application/json', body=body)
        except ValueError:
            the_log.exception(f"Incorrect syntax: {req.body}")
            return Response(status=400)
        except AttributeError:
            the_log.exception(f"OpenFlow request with this version {dpath.ofproto.OFP_VERSION} is not supported.")
            return Response(status=501)

    return wrapper


# Handle the commands to parse JSON data to manage flows
def command_devices(method):
    # Decorator function to handle the functions mapped to the API URIs
    def wrapper(self, req, *args, **kwargs):
        try:
            if req.body:
                """From the original ofctl_rest application, it uses ast.literal_eval()
                for parsing the JSON body because it is needed to parse the body in
                binary format."""
                the_body = ast.literal_eval(req.body.decode('utf-8'))
            else:
                the_body = {}
        except SyntaxError:
            the_log.exception(f"Syntax Invalid: {req.body}")
            return Response(status=400)
        # Getting the datapath ID from the request parameters that the client provides
        of_dpid = the_body.get('dpid', None)
        if not of_dpid:
            try:
                of_dpid = kwargs.pop('dpid')
            except KeyError:
                the_log.exception("Could not retrieve dpid from the API request")
                return Response(status=400)
        # Get the datapath instance of the device from the DPSet
        try:
            # dp = int(str(of_dpid), 0)
            dpath = self.dpset.get(int(str(of_dpid), 0))
        except ValueError:
            the_log.exception(f"DPID {of_dpid} is invalid")
            return Response(status=400)
        if dpath is None:
            the_log.error(f"Datapath {of_dpid} does not exist.")
            return Response(status=404)
        # Get the ofctl version
        try:
            of_version = supported_of_versions.get(dpath.ofproto.OFP_VERSION)
        except KeyError:
            the_log.exception(f"OpenFlow Version {dpath.ofproto.OFP_VERSION} is unsupported, use OpenFlow 1.3 or 1.5")
            return Response(status=501)
        # invoke the InfoController method, similar to device_data
        try:
            method(self, req, dpath, of_version, the_body, *args, **kwargs)
            return Response(status=200)
        except ValueError:
            the_log.exception(f"Invalid syntax {req.body}")
            return Response(status=400)
        except AttributeError:
            the_log.exception(f"OpenFlow version {dpath.ofproto.OFP_VERSION} is unsupported, use OpenFlow 1.3 or 1.5")
            return Response(status=501)
        except NotValidCommand as e:
            the_log.exception(e.message)
            return Response(status=404)
        except NonExistentPort as e:
            the_log.exception(e.message)
            return Response(status=404)

    return wrapper


class InfoController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(InfoController, self).__init__(req, link, data, **config)
        self.dpset = data["dpset"]
        self.waiters = data["waiters"]

    # Get the datapath IDs of the OpenFlow devices
    def retrieve_dpids(self, request, **_kwargs):
        """Get the DPIDs of all the OpenFlow switches"""
        dps = list(self.dpset.dps.keys())
        data_body = json.dumps(dps)
        return Response(content_type="application/json", body=data_body)

    # Now to make the API calls

    # *** Start of the @device_data functions ***
    @device_data
    def get_stats_description(self, req, dpath, of_version, **_kwargs):
        """Get a general description of an OpenFlow switch"""
        return of_version.get_desc_stats(dpath, self.waiters)

    @device_data
    def get_flow_info(self, req, dpath, of_version, **_kwargs):
        """Gets the flow information from an OpenFlow switch"""
        flow = req.json if req.body else {}
        return of_version.get_flow_stats(dpath, self.waiters, flow)

    @device_data
    def aggregate_flows(self, req, dpath, of_version, **_kwargs):
        """Get the aggregate/total flows from an OpenFlow switch"""
        flow = req.json if req.body else {}
        return of_version.get_aggregate_flow_stats(dpath, self.waiters, flow)

    @device_data
    def flow_table_info(self, req, dpath, of_version, **_kwargs):
        """Get the stats from the flow tables of an OpenFlow switch"""
        return of_version.get_table_stats(dpath, self.waiters)

    @device_data
    def flow_table_features(self, req, dpath, of_version, **_kwargs):
        """Get the flow table features of an OpenFlow switch"""
        return of_version.get_table_features(dpath, self.waiters)

    @device_data
    def port_information(self, req, dpath, of_version, port=None, **_kwargs):
        """Get the stats of a port from an OpenFlow switch"""
        if port == 'ALL':
            port = None
        return of_version.get_port_stats(dpath, self.waiters, port)

    @device_data
    def queue_information(self, req, dpath, of_version, port=None, queue_id=None, **_kwargs):
        """Get the queue stats from an OpenFlow switch"""
        if port == "ALL":
            port = None
        if queue_id == "ALL":
            queue_id = None
        return of_version.get_queue_stats(dpath, self.waiters, port, queue_id)

    @device_data
    def queue_configuration(self, req, dpath, of_version, port=None, queue=None, **_kwargs):
        """Get the queue configuration from an OpenFlow switch"""
        if port == "ALL":
            port = None
        return of_version.get_queue_config(dpath, self.waiters, port)

    @device_data
    def meter_specs(self, req, dpath, of_version, **_kwargs):
        """Get the table meter features from an OpenFlow switch"""
        return of_version.get_meter_features(dpath, self.waiters)

    @device_data
    def meter_configuration(self, req, dpath, of_version, meterID=None, **_kwargs):
        """Get the table meter configuration from an Openflow switch"""
        if meterID == "ALL":
            meterID = None
        return of_version.get_meter_config(dpath, self.waiters, meterID)

    @device_data
    def meter_info(self, req, dpath, of_version, meterID=None, **_kwargs):
        """This gets the information about a meter of an OpenFlow switch"""
        if meterID == "ALL":
            meterID = None
        return of_version.get_meter_stats(dpath, self.waiters, meterID)

    @device_data
    def group_specs(self, req, dpath, of_version, groupID, **_kwargs):
        """Gets the group table statistics of an OpenFlow switch"""
        if groupID == "ALL":
            groupID = None
        return of_version.get_group_stats(dpath, self.waiters, groupID)

    @device_data
    def group_description(self, req, dpath, of_version, groupID=None, **_kwargs):
        """Get the group table description of an OpenFlow switch"""
        return of_version.get_group_desc(dpath, self.waiters)

    @device_data
    def group_info(self, req, dpath, of_version, **_kwargs):
        """Get the features of a group table from an OpenFlow switch"""
        return of_version.get_group_features(dpath, self.waiters)

    @device_data
    def port_description(self, req, dpath, of_version, **_kwargs):
        """Get port description info from an OpenFlow switch"""
        return of_version.get_port_desc(dpath, self.waiters)

    @device_data
    def controler_role(self, req, dpath, of_version, **_kwargs):
        """Get the current role of the controller from an OpenFlow switch"""
        return of_version.get_role(dpath, self.waiters)

    # *** End of the @device_data functions ***

    # *** Start of the @command_devices functions ***

    @command_devices
    def manage_flow_entry(self, req, dpath, of_version, flow, command, **kwargs):
        """This function is used to manage an OpenFlow flow entry to an OpenFlow switch.
        It gives you the five options of ADD, MODIFY, MODIFY STRICT, DELETE, DELETE STRICT.
        These command options are used to modify flows on a flow table. The ADD adds in a
        new flow, MODIFY changes all the matching flows, MODIFY_STRICT changes flows that match specific
        wildcars and the priority, DELETE deletes all the matching flows, and DELETE_STRICT deletes flows
        that match specific wildcard values and priority."""

        # Map a keyword to an OpenFlow command
        cmd_dictionary = {
            'add': dpath.ofproto.OFPFC_ADD,
            'change_all': dpath.ofproto.OFPFC_MODIFY,
            'change_strict': dpath.ofproto.OFPFC_MODIFY_STRICT,
            'delete_all': dpath.ofproto.OFPFC_DELETE,
            'delete_strict': dpath.ofproto.OFPFC_DELETE_STRICT
        }
        # Check to see if user is using a valid command
        cmd = cmd_dictionary.get(command, None)
        if cmd is None:
            raise NotValidCommand(command=command)
        of_version.mod_flow_entry(dpath, flow, cmd)

    @command_devices
    def clear_flows(self, req, dpath, of_version, flow, **_kwargs):
        """This erases all of the flows on an OpenFlow switch"""
        flow = {'table_id': dpath.ofproto.OFPTT_ALL}
        of_version.mod_flow_entry(dpath, flow, dpath.ofproto.OFPFC_DELETE)

    @command_devices
    def manage_meters(self, req, dpath, of_version, meter, command, **_kwargs):
        """Manage the meter entries on an OpenFlow switch"""
        cmd_dictionary = {
            'add': dpath.ofproto.OFPMC_ADD,
            'change': dpath.ofproto.OFPMC_MODIFY,
            'remove': dpath.ofproto.OFPMC_DELETE
        }
        cmd = cmd_dictionary.get(command, None)
        if cmd is None:
            raise NotValidCommand(command=command)
        of_version.mod_meter_entry(dpath, meter, cmd)

    @command_devices
    def manage_group(self, req, dpath, of_version, group, command, **_kwargs):
        """This manages the group entries on an OpenFlow switch"""
        cmd_dictionary = {
            'add': dpath.ofproto.OFPGC_ADD,
            'change': dpath.ofproto.OFPGC_MODIFY,
            'remove': dpath.ofproto.OFPGC_DELETE
        }
        cmd = cmd_dictionary.get(command, None)
        if cmd is None:
            raise NotValidCommand(command=command)
        of_version.mod_group_entry(dpath, group, cmd)

    @command_devices
    def manage_ports(self, req, dpath, of_version, port, command, **_kwargs):
        """This manages the port behavior of an OpenFlow switch"""
        port_number = port.get('port_no', None)
        port_number = int(str(port_number), 0)  # Gets the port number

        port_information = self.dpset.port_state[int(dpath.id)].get(port_number)
        if port_information:
            port.setdefault('hw_addr', port_information.hw_addr)

            """Check if the switch is using OpenFlow 1.3"""
            if dpath.ofproto.OFP_VERSION == ofproto_v1_3.OFP_VERSION:
                port.setdefault('advertise', port_information.advertised)
            else:
                port.setdefault('properties', port_information.properties)
        else:
            raise NonExistentPort(port_no=port_number)
        if command != 'modify':
            raise NotValidCommand(command=command)
        of_version.mod_port_behavior(dpath, port)

    @command_devices
    def experimenter(self, req, dpath, of_version, exp_message, **_kwargs):
        """Send an experimenter message to the OpenFlow switch"""
        of_version.send_experimenter(dpath, exp_message)

    @command_devices
    def update_role(self, req, dpath, of_version, role, **_kwargs):
        """Change the role of the OpenFlow switch"""
        of_version.set_role(dpath, role)


# The actual REST API class that maps the URIs to the functions to run
class RestApi(app_manager.RyuApp):
    # Supported OpenFlow versions
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # setup the contexts, WSGIApplication is the web server feature of Ryu
    _CONTEXTS = {
        'dpset': dpset.DPSet,
        'the_wsgi': WSGIApplication
    }

    def __init__(self, *args, **kwargs):
        super(RestApi, self).__init__(*args, **kwargs)
        self.dpset = kwargs['dpset']  # gets set of datapath instances of OpenFlow devices
        wsgi = kwargs['the_wsgi']  # gets the WSGI web server info
        self.waiters = {}
        self.data = {}
        self.data['dpset'] = self.dpset
        self.data['waiters'] = self.waiters
        mapping = wsgi.mapper

        # Setup the WSGI URI mappings

        # *** Start of the @device_data GET request API URIs ***
        wsgi.registory['InfoController'] = self.data
        path = '/info'
        uri = path + '/switches'
        mapping.connect('info', uri, controller=InfoController,
                        action='retrieve_dpids', conditions=dict(method=['GET']))

        uri = path + '/desc/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='get_stats_description', conditions=dict(method=['GET']))

        uri = path + '/flows/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='get_flow_info', conditions=dict(method=['GET', 'POST']))

        uri = path + '/aggregateflows/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='aggregate_flows', conditions=dict(method=['GET', 'POST']))

        uri = path + '/flowtables/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='flow_table_info', conditions=dict(method=['GET']))

        uri = path + '/flowtablefeatures/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='flow_table_features', conditions=dict(method=['GET']))

        uri = path + '/portinfo/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='port_information', conditions=dict(method=['GET']))

        uri = path + '/portinfo/{dpid}/{port}'
        mapping.connect('info', uri, controller=InfoController,
                        action='port_information', conditions=dict(method=['GET']))

        uri = path + '/queueinfo/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='queue_information', conditions=dict(method=['GET']))

        uri = path + '/queueinfo/{dpid}/{port}'
        mapping.connect('info', uri, controller=InfoController,
                        action='queue_information', conditions=dict(method=['GET']))

        uri = path + '/queueinfo/{dpid}/{port}/{queue_id}'
        mapping.connect('info', uri, controller=InfoController,
                        action='queue_information', conditions=dict(method=['GET']))

        uri = path + '/queueconfiguration/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='queue_configuration', conditions=dict(method=['GET']))

        uri = path + '/queueconfiguration/{dpid}/{port}'
        mapping.connect('info', uri, controller=InfoController,
                        action='queue_configuration', conditions=dict(method=['GET']))

        uri = path + '/queueconfiguration/{dpid}/{port}/{queue}'
        mapping.connect('info', uri, controller=InfoController,
                        action='queue_description', conditions=dict(method=['GET']))

        uri = path + '/meterspecs/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='meter_specs', conditions=dict(method=['GET']))

        uri = path + '/meterconfiguration/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='meter_configuration', conditions=dict(method=['GET']))

        uri = path + '/meterconfiguration/{dpid}/{meterID}'
        mapping.connect('info', uri, controller=InfoController,
                        action='meter_configuration', conditions=dict(method=['GET']))

        uri = path + '/meterinfo/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='meter_info', conditions=dict(method=['GET']))

        uri = path + '/meterinfo/{dpid}/{meterID}'
        mapping.connect('info', uri, controller=InfoController,
                        action='meter_info', conditions=dict(method=['GET']))

        uri = path + '/group/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='group_specs', conditions=dict(method=['GET']))

        uri = path + '/group/{dpid}/{groupID}'
        mapping.connect('info', uri, controller=InfoController,
                        action='group_specs', conditions=dict(method=['GET']))

        uri = path + '/groupdescription/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='group_description', conditions=dict(method=['GET']))

        uri = path + '/groupdescription/{dpid}/{groupID}'
        mapping.connect('info', uri, controller=InfoController,
                        action='group_description', conditions=dict(method=['GET']))

        uri = path + '/portdescription/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='port_description', conditions=dict(method=['GET']))

        uri = path + '/currentrole/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='controler_role', conditions=dict(method=['GET']))
        # *** End of the @device_data GET request API URIs ***

        # *** Start of the @command_devices POST PUT and DELETE request API URIs ***
        uri = path + '/ryuflow/{command}'
        mapping.connect('info', uri, controller=InfoController,
                        action='manage_flow_entry', conditions=dict(method=['POST', 'PUT', 'DELETE']))

        uri = path + '/flows/erase/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='clear_flows', conditions=dict(method=['DELETE']))

        uri = path + '/meter/{command}'
        mapping.connect('info', uri, controller=InfoController,
                        action='manage_meters', conditions=dict(method=['POST', 'PUT', 'DELETE']))

        uri = path + '/group/{command}'
        mapping.connect('info', uri, controller=InfoController,
                        action='manage_group', conditions=dict(method=['POST', 'PUT', 'DELETE']))

        uri = path + '/portbehavior/{command}'
        mapping.connect('info', uri, controller=InfoController,
                        action='manage_ports', conditions=dict(method=['PUT']))

        uri = path + '/sendexperimenter/{dpid}'
        mapping.connect('info', uri, controller=InfoController,
                        action='experimenter', conditions=dict(method=['POST']))

        uri = path + '/updaterole'
        mapping.connect('info', uri, controller=InfoController,
                        action='update_role', conditions=dict(method=['PUT']))
        # *** End of the @command_devices POST PUT and DELETE request API URIs ***

        # handle the OpenFlow event replies

    @set_ev_cls([ofp_event.EventOFPStatsReply,
                 ofp_event.EventOFPDescStatsReply,
                 ofp_event.EventOFPFlowStatsReply,
                 ofp_event.EventOFPAggregateStatsReply,
                 ofp_event.EventOFPTableStatsReply,
                 ofp_event.EventOFPTableFeaturesStatsReply,
                 ofp_event.EventOFPPortStatsReply,
                 ofp_event.EventOFPQueueStatsReply,
                 ofp_event.EventOFPQueueDescStatsReply,
                 ofp_event.EventOFPMeterStatsReply,
                 ofp_event.EventOFPMeterFeaturesStatsReply,
                 ofp_event.EventOFPMeterConfigStatsReply,
                 ofp_event.EventOFPGroupStatsReply,
                 ofp_event.EventOFPGroupFeaturesStatsReply,
                 ofp_event.EventOFPGroupDescStatsReply,
                 ofp_event.EventOFPPortDescStatsReply
                 ], MAIN_DISPATCHER)
    def reply_manager(self, ev):
        print('')
        print("Running stats reply")
        message = ev.msg
        dpath = message.datapath

        if dpath.id not in self.waiters:
            return
        """The xid, or transaction ID is used to match requests to responses."""
        if message.xid not in self.waiters[dpath.id]:
            return
        lock, messages = self.waiters[dpath.id][message.xid]
        messages.append(message)
        flags = 0
        flags = dpath.ofproto.OFPMPF_REPLY_MORE

        if message.flags & flags:
            return
        del self.waiters[dpath.id][message.xid]
        lock.set()

    @set_ev_cls([ofp_event.EventOFPSwitchFeatures,
                 ofp_event.EventOFPQueueGetConfigReply,
                 ofp_event.EventOFPRoleReply], MAIN_DISPATCHER)
    def features_reply(self, ev):
        """Function that handles the OpenFlow reply messages"""
        print('')
        print("Running Features Reply!")
        message = ev.msg
        dpath = message.datapath
        if dpath.id not in self.waiters:
            return
        if message.xid not in self.waiters[dpath.id]:
            return
        lock, messages = self.waiters[dpath.id][message.xid]
        messages.append(message)

        del self.waiters[dpath.id][message.xid]
        lock.set()