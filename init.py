# Write a simple controller program to implement the static router function
# Respond to ARP requests from the host
# Forward at the IP layer based on the static routing table
# Respond to an ICMP echo request to the router itself
# For IP packets that fail to match the routing table, an ICMP network unreachable packet is sent
from ryu.base import app_manager

from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3


from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow.libopenflow_01 import *
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.packet import ethernet
from pox.lib.packet.ethernet import ETHER_ANY, ETHER_BROADCAST
from pox.lib.packet import arp, ipv4, icmp
from pox.lib.packet.icmp import TYPE_ECHO_REQUEST, TYPE_ECHO_REPLY,\
                                 TYPE_DEST_UNREACH, CODE_UNREACH_NET, CODE_UNREACH_HOST

log = core.getLogger()

# arp mapping table
# The structure is { dpid1:{ port_no1:{ ip1:mac1 , ip1:mac2 , ... } , port_no2:{ ... } , ... } , dpid2:{ ... } , ... }
arpTable = {}
#Port mapping table
# The structure is { dpid : [ [ port_no1 , mac1 , ip1 ] , [ port_no2 , mac2 , ip2 ] , dpid2 : ... ] }
portTable = {}

#Routing table constants
# The structure is: [[network, next-hop ip address, next-hop interface name, next-hop interface ip, next-hop port], [...],...]
rDST_NETWORK = 0
rNEXTHOP_IP = 1
rNEXTHOP_PORT_NAME = 2
rNEXTHOP_PORT_IP = 3
rNEXTHOP_PORT = 4

#Port mapping table constants
# Record the router's own port, IP and mac mapping
# The structure is { dpid : [ [ port_no1 , mac1 , ip1 ] , [ port_no2 , mac2 , ip2 ] , dpid2 : ... ] }
pPORT = 0
pPORT_MAC = 1
pPORT_IP = 2

class routerConnection(object):

  def __init__(self,connection):
    dpid = connection.dpid
    log.debug('-' * 50 + "dpid=" + str(dpid) + '-' * 50)
    log.debug('-' * 50 + "I\'m a StaticRouter" + '-' * 50)

    # Initialize arp mapping table
    arpTable[dpid] = {}
    #Initialize port mapping table
    portTable[dpid] = []

    #Generate arp table and port mapping table based on features_reply package
    for entry in connection.ports.values():
      port = entry.port_no
      mac = entry.hw_addr
      # Do not generate arp tables for router and controller ports
      if port <= of.ofp_port_rev_map['OFPP_MAX']:
        arpTable[dpid][port] = {}
        if port == 1:
          ip = IPAddr('10.0.1.1')
          arpTable[dpid][port][ip] = mac
          portTable[dpid].append([port, mac, ip])
        elif port == 2:
          ip = IPAddr('10.0.2.1')
          arpTable[dpid][port][ip] = mac
          portTable[dpid].append([port, mac, ip])
        elif port == 3:
          ip = IPAddr('10.0.3.1')
          arpTable[dpid][port][ip] = mac
          portTable[dpid].append([port, mac, ip])
        else:
          ip = IPAddr('0.0.0.0') # No ip assigned
          arpTable[dpid][port][ip] = mac
          portTable[dpid].append([port, mac, ip])
class MyController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MyController, self).__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Add your logic here to handle switch features
        # For example, install a default flow entry

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id, priority=priority,
                                    match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

def main():
    from ryu.cmd import manager
    manager.main()

if __name__ == "__main__":
    main()
