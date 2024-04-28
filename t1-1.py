
from mininet.net import Mininet
from mininet.node import Controller
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def emptyNet():

    "Create an empty network and add nodes to it."

    net = Mininet()

    # net.addController('c0',controller=RemoteController,ip="127.0.0.1",port=6653)
    info( '*** Adding controller\n' )

    info( '*** Adding switch\n' )
    s1 = net.addSwitch( 's1' )
    s2 = net.addSwitch( 's2' )
    s3 = net.addSwitch( 's3' )
    s4 = net.addSwitch( 's4' )
    s5 = net.addSwitch('s5')


    info( '*** Creating links\n' )
    net.addLink( s1, s2 )
    net.addLink( s2, s3 )
    net.addLink( s3, s4 )
    net.addLink( s4, s5 )
    net.addLink( s5, s1 )
    info( '*** Starting network\n')
    net.start()

    info( '*** Running CLI\n' )
    CLI( net )


if __name__ == '__main__':
    setLogLevel( 'info' )
    emptyNet()


def add_flow(self, datapath, priority, match, actions, buffer_id=None):
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser

    inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                         actions)]
    if buffer_id:
        mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                priority=priority, match=match,
                                instructions=inst)
    else:
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
    datapath.send_msg(mod)


def del_flow(self, datapath, match):
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser

    cookie = cookie_mask = 0
    table_id = 0
    idle_timeout = hard_timeout = 0
    buffer_id = ofproto.OFP_NO_BUFFER
    actions = []
    inst = []
    req = parser.OFPFlowMod(datapath, match=match, command=ofproto.OFPFC_DELETE, out_port=ofproto.OFPG_ANY,
                            out_group=ofproto.OFPG_ANY)

    datapath.send_msg(req)