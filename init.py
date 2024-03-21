# Write a simple controller program to implement the static router function
# Respond to ARP requests from the host
# Forward at the IP layer based on the static routing table
# Respond to an ICMP echo request to the router itself
# For IP packets that fail to match the routing table, an ICMP network unreachable packet is sent



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

          #Print arp table
          log.debug('-' * 50 + 'arpTable' + '-' * 50)
          log.debug(arpTable)

          #Print port mapping table
          log.debug('-' * 50 + 'portTable' + '-' * 50)
          log.debug(portTable)

          # iprouting-table
          # The structure is: [[network, next-hop ip address, next-hop interface name, next-hop interface ip, next-hop port], [...],...]
          # The next hop IP is 0.0.0.0, which means direct deliveryself.routeTable = []
        self.routeTable.append(['10.0.1.0/24',
                                  '0.0.0.0', 's1-eth1', '10.0.1.1', 1])
        self.routeTable.append(['10.0.2.0/24',
                                  '10.0.2.100', 's1-eth2', '10.0.2.1', 2])
        self.routeTable.append(['10.0.3.0/24',
                                  '10.0.3.100', 's1-eth3', '10.0.3.1', 3])

        self.connection = connection
        connection.addListeners(self)

        #Stream delete messages

      def _handle_FlowRemoved(self, event):
          dpid = event.connection.dpid
          log.debug('-' * 50 + "dpid=" + str(dpid) + '-' * 50)
          log.debug('A FlowRemoved Message Recieved')
          log.debug('---A flow has been removed')

      # PackerIn messages
      def _handle_PacketIn(self, event):
          dpid = self.connection.dpid
          log.debug('-' * 50 + "dpid=" + str(dpid) + '-' * 50)
          log.debug("A PacketIn Message Recieved")
          packet = event.parsed

          # arp
          if packet.type == ethernet.ARP_TYPE:
              log.debug('---It\'s an arp packet')
              arppacket = packet.payload
              # arp response
              if arppacket.opcode == arp.REPLY:
                  arpTable[self.connection.dpid][event.ofp.in_port][arppacket.protosrc] = arppacket.hwsrc
                  arpTable[self.connection.dpid][event.ofp.in_port][arppacket.protodst] = arppacket.hwdst
                  #Updated arp table
                  log.debug('------arpTable learned form arp Reply srt and dst')
                  log.debug('------' + str(arpTable))

              # arp request
              if arppacket.opcode == arp.REQUEST:
                  log.debug('------Arp request')
                  log.debug('------' + arppacket._to_str())
                  arpTable[self.connection.dpid][event.ofp.in_port][arppacket.protosrc] = arppacket.hwsrc
                  #Updated arp table
                  log.debug('------arpTable learned form arp Request srt')
                  log.debug('------' + str(arpTable))

                  #Send arp response
                  if arppacket.protodst in arpTable[self.connection.dpid][event.ofp.in_port]:
                      log.debug('------I know that ip %s,send reply' % arppacket.protodst)

                      # Construct arp response
                      a = arppacket
                      r = arp()
                      r.hwtype = a.hwtype
                      r.prototype = a.prototype
                      r.hwlen = a.hwlen
                      r.protolen = a.protolen
                      r.opcode = arp.REPLY
                      r.hwdst = a.hwsrc
                      r.protodst = a.protosrc
                      r.protosrc = a.protodst
                      r.hwsrc = arpTable[self.connection.dpid][event.ofp.in_port][arppacket.protodst]
                      e = ethernet(type=packet.type, src=r.hwsrc, dst=a.hwsrc)
                      e.set_payload(r)
                      msg = of.ofp_packet_out()
                      msg.data = e.pack()
                      msg.actions.append(of.ofp_action_output(port=event.ofp.in_port))
                      self.connection.send(msg)
              #ip package
          if packet.type == ethernet.IP_TYPE:
              log.debug('---It\'s an ip packet')
              ippacket = packet.payload
              # destination ip
              dstip = ippacket.dstip

              # Search the port mapping table, determine whether the destination IP is the router itself, and respond to icmp echo reply
              for t in portTable[dpid]:
                  selfip = t[pPORT_IP]
                  # If the destination IP address is the address owned by the current router
                  if dstip == selfip:
                      # If it is an icmp echo request message
                      if ippacket.protocol == ipv4.ICMP_PROTOCOL:
                          log.debug('!!!!!!!!!!An icmp for me!!!!!!!!!!!')
                          icmppacket = ippacket.payload
                          # Is it icmp echo request?
                          if icmppacket.type == TYPE_ECHO_REQUEST:
                              selfmac = t[pPORT_MAC]
                              log.debug('!!!!!!!!!!An icmp echo request for me!!!!!!!!!!!')

                              # Construct icmp package
                              r = icmppacket
                              r.type = TYPE_ECHO_REPLY

                              # Construct ip package
                              s = ipv4()
                              s.protocol = ipv4.ICMP_PROTOCOL
                              s.srcip = selfip
                              s.dstip = ippacket.srcip
                              s.payload = r

                              # Construct Ethernet frame
                              e = ethernet()
                              e.type = ethernet.IP_TYPE
                              e.src = selfmac
                              e.dst = packet.src
                              e.payload = s

                              # Construct PacketOut message
                              # Send back icmp packet
                              msg = of.ofp_packet_out()
                              msg.data = e.pack()
                              msg.actions.append(of.ofp_action_output(port=event.port))
                              self.connection.send(msg)
                              log.debug('!!!!!!!!!!Reply it!!!!!!!!!!!')
                              return
                          else:
                              # Ignore all icmp packets sent to the router except icmp echo request.
                              return
                      # Non-icmp packets sent to the router
                      else:
                          # Lose packets directly, the controller will not respond temporarily.
                          return
