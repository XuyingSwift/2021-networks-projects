from collections import defaultdict
import queue
import threading


## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    def __init__(self, maxsize=0):
        self.in_queue = queue.Queue(maxsize)
        self.out_queue = queue.Queue(maxsize)

    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None

    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
            # print('putting packet in the OUT queue')
            self.out_queue.put(pkt, block)
        else:
            # print('putting packet in the IN queue')
            self.in_queue.put(pkt, block)


## Implements a network layer packet.
class NetworkPacket:
    ## packet encoding lengths
    dst_S_length = 5
    prot_S_length = 1

    ##@param dst: address of the destination host
    # @param data_S: packet payload
    # @param prot_S: upper layer protocol for the packet (data, or control)
    def __init__(self, dst, prot_S, data_S):
        self.dst = dst
        self.data_S = data_S
        self.prot_S = prot_S

    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()

    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst).zfill(self.dst_S_length)
        if self.prot_S == 'data':
            byte_S += '1'
        elif self.prot_S == 'control':
            byte_S += '2'
        else:
            raise ('%s: unknown prot_S option: %s' % (self, self.prot_S))
        byte_S += self.data_S
        return byte_S

    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst = byte_S[0: NetworkPacket.dst_S_length].strip('0')
        prot_S = byte_S[NetworkPacket.dst_S_length: NetworkPacket.dst_S_length + NetworkPacket.prot_S_length]
        if prot_S == '1':
            prot_S = 'data'
        elif prot_S == '2':
            prot_S = 'control'
        else:
            raise ('%s: unknown prot_S field: %s' % (self, prot_S))
        data_S = byte_S[NetworkPacket.dst_S_length + NetworkPacket.prot_S_length:]
        return self(dst, prot_S, data_S)


## Implements a network host for receiving and transmitting data
class Host:

    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False  # for thread termination

    ## called when printing the object
    def __str__(self):
        return self.addr

    ## create a packet and enqueue for transmission
    # @param dst: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst, data_S):
        p = NetworkPacket(dst, 'data', data_S)
        print('%s: sending packet "%s"' % (self, p))
        self.intf_L[0].put(p.to_byte_S(), 'out')  # send packets always enqueued successfully

    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.intf_L[0].get('in')
        if pkt_S is not None:
            print('%s: received packet "%s"' % (self, pkt_S))

    ## thread target for the host to keep receiving data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            # receive data arriving to the in interface
            self.udt_receive()
            # terminate
            if (self.stop):
                print(threading.currentThread().getName() + ': Ending')
                return


## Implements a multi-interface router
class Router:

    ##@param name: friendly router name for debugging
    # @param cost_D: cost table to neighbors {neighbor: {interface: cost}}
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, cost_D, max_queue_size):
        self.stop = False  # for thread termination
        self.name = name
        # create a list of interfaces
        self.intf_L = [Interface(max_queue_size) for _ in range(len(cost_D))]
        # save neighbors and interfaces on which we connect to them
        self.cost_D = cost_D  # {neighbor: {interface: cost}}
        self.total_rt = defaultdict(dict)

        self.rt_tbl_D = cost_D.copy()

        print("routing table in constructor: ", self.rt_tbl_D)
        print('%s: Initialized routing table' % self)
        self.print_routes()

    ## Print routing table
    def print_routes(self):

        print('\n%s: sending packet' % (self))

        # for horizontal edges
        horizontal_edge = '+==='
        for i in range(len(self.rt_tbl_D.keys())):
            horizontal_edge += '+=='
        horizontal_edge += '+'
        print(horizontal_edge)

        # for header (destinations)
        header = '|' + self.name + ' |'
        for dest in self.rt_tbl_D.keys():
            header += dest + ' |'
        print(header)
        print(horizontal_edge)

        # for routers costs at destinations
        interior = '|' + self.name + ' | '
        for value in self.rt_tbl_D.values():
            for y in value.values():
                interior += str(y) + ' | '
        print(interior)
        print(horizontal_edge, '\n')

    ## called when printing the object
    def __str__(self):
        return self.name

    ## look through the content of incoming interfaces and
    # process data and control packets
    def process_queues(self):
        for i in range(len(self.intf_L)):
            pkt_S = None
            # get packet from interface i
            pkt_S = self.intf_L[i].get('in')
            # if packet exists make a forwarding decision
            if pkt_S is not None:
                p = NetworkPacket.from_byte_S(pkt_S)  # parse a packet out
                if p.prot_S == 'data':
                    self.forward_packet(p, i)
                elif p.prot_S == 'control':
                    self.update_routes(p, i)
                else:
                    raise Exception('%s: Unknown packet type in packet %s' % (self, p))

    ## forward the packet according to the routing table
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def forward_packet(self, p, i):
        try:
            # TODO: Here you will need to implement a lookup into the
            # forwarding table to find the appropriate outgoing interface
            # for now we assume the outgoing interface is 1

            # loop up for detination in routing table
            route = self.rt_tbl_D.get(str(p.dst))
            # loop up which interface to forward to
            #for interface, cost in route.items():
                #j = int(interface)
            #self.intf_L[1].put(p.to_byte_S(), 'out', True)
            print('%s: forwarding packet "%s" from interface %d to %d' % \
                  (self, p, i, 1))
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass

    ## send out route update
    # @param i Interface number on which to send out a routing update
    def send_routes(self, i): # encoding, name///Node/Link/cost//node/link/cost//....
        # string more message in packet
        routing_table = self.name + "///"
        # iterate through dictionary for router, neighbor and cost
        for k, v in self.rt_tbl_D.items():
            for neighbor, cost in v.items():
                # Encodes the string so we can separate route
                # from neighbor and cost, and distinguish routes with a slash
                routing_table += str(k) + "/" + str(neighbor) + "/" + str(cost) + "//"
                print(k, neighbor, cost)
        # create a routing table update packet
        p = NetworkPacket(0, 'control', routing_table)
        try:
            print('%s: sending routing update "%s" from interface %d' % (self, p, i))
            self.intf_L[i].put(p.to_byte_S(), 'out', True)
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass

    ## forward the packet according to the routing table
    #  @param p Packet containing routing information
    def update_routes(self, p, i):
        # Initialize to false, as we haven't updated yet
        updated = False
        # we decode the packet
        table = p.data_S.split("///")
        name_table = table[0]
        routes = table[1].split("//")
        # Splits up the info of a route
        for route in routes:
            if route != '':
                node = route.split("/")

            # Adds to global table
            self.total_rt[name_table][node[0]] = [int(node[2])]

            # Check if node is current router, if so, set distance & skip
            if node[0] == self.name:

                # Grabs the interface of the neighbor
                inf =  list(self.cost_D[name_table].keys())
                # Distance of the new node to neighbor and distance from neighbor to node
                self.rt_tbl_D[node[0]] = {int(inf[0]): 0}
                # Adds to global table
                self.total_rt[self.name][node[0]] = [0]

                continue

            # Checks if the node is not already in the table or not a neighbor
            if node[0] not in self.cost_D and  node[0] not in self.rt_tbl_D:

                # Grabs the distance of the neighbor
                n = list(self.cost_D[name_table].values())
                # Grabs the interface of the neighbor
                inf = list(self.cost_D[name_table].keys())
                # Distance to new node
                self.rt_tbl_D[node[0]] = {int(inf[0]):int(node[2]) + n[0]}
                # Adds to global table
                self.total_rt[self.name][node[0]] = [int(node[2]) + n[0]]
                # We have now updated the list
                updated = True

            elif node[0] not in self.cost_D and  node[0] in self.rt_tbl_D:
                # Grabs the distance of the neighbor
                n = list(self.cost_D[name_table].values())
                # Gets the interface of that neighbor
                inf = list(self.cost_D[name_table].keys())
                # Gets the current distance
                curr = list(self.rt_tbl_D[node[0]].values())
                # Checks if the current distance is greater than the new distance
                if curr[0] > int(n[0]) + int(node[2]):
                    self.rt_tbl_D[node[0]] = {int(inf[0]):int(node[2]) + n[0]}
                    # Adds to global table
                    self.total_rt[self.name][node[0]] = [int(node[2]) + n[0]]
                    # List has been updated
                    updated = True

        # Notifies neighbor's if we have updated
        if updated:
            for neighbor_name, neighbor_info in self.cost_D.items():
                for interface,cost in neighbor_info.items():
                    # Checks if the neighbor is a host
                    if 'H' not in neighbor_name:
                        self.send_routes(interface)


    ## thread target for the host to keep forwarding data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print(threading.currentThread().getName() + ': Ending')
                return