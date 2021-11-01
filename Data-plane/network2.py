
import queue
import threading


## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    def __init__(self, maxsize=0):
        self.queue = queue.Queue(maxsize);
        self.mtu = None

    ##get packet from the queue interface
    def get(self):
        try:
            return self.queue.get(False)
        except queue.Empty:
            return None

    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, block=False):
        self.queue.put(pkt, block)


## Implements a network layer packet (different from the RDT packet
# from programming assignment 2).
# NOTE: This class will need to be extended to for the packet to include
# the fields necessary for the completion of this assignment.
class NetworkPacket:
    ## packet encoding lengths
    dst_addr_S_length = 5

    # allow the destination host to perform tasks
    offset_S_length = 2
    flag_S_length = 1
    header_length = dst_addr_S_length + flag_S_length + offset_S_length

    ##@param dst_addr: address of the destination host
    # @param data_S: packet payload
    # pass int  takes in flag and offset
    def __init__(self, dst_addr, data_S, flag=0, offset=0):
        self.dst_addr = dst_addr
        self.data_S = data_S

        # new parameters
        self.offset = offset
        self.flag = flag  # flag bit,  the last segment should have a flag bit of zero

    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()

    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst_addr).zfill(self.dst_addr_S_length)
        byte_S += self.data_S
        return byte_S

    # convert packet into a byte string segment for transmission over links
        byte_S = str(self.dst_addr).zfill(self.dst_addr_S_length)
        byte_S += str(self.flag).zfill(self.flag_S_length)
        byte_S += str(self.offset).zfill(self.offset_S_length)
        byte_S += self.data_S
        return byte_S

    @classmethod
    def is_segment(cls, byte_S):
        if byte_S[cls.dst_addr_S_length] == 1:
            return True
        return False

    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S, mtu):
        # store segment
        packets = []
        dst_addr = int(byte_S[0: NetworkPacket.dst_addr_S_length])
        data_S = byte_S[NetworkPacket.dst_addr_S_length:]

        # segments
        offset_size = 0
        while True:
            # set seg_flag to 1
            seg_flag = 1 if self.header_length + len(
                data_S[offset_size:]) > mtu else 0
            # add segment to packet
            packets.append(self(dst_addr, data_S[offset_size:offset_size + mtu - self.header_length], seg_flag,
                                offset_size))
            offset_size = offset_size + mtu - self.header_length
            if len(data_S[offset_size:]) == 0:
                break
        return packets


## Implements a network host for receiving and transmitting data
class Host:

    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.in_intf_L = [Interface()]
        self.out_intf_L = [Interface()]
        self.stop = False  # for thread termination

    ## called when printing the object
    def __str__(self):
        return 'Host_%s' % (self.addr)

    ## create a packet and enqueue for transmission
    # @param dst_addr: destination address for the packet
    # @param data_S: data being transmitted to the network layer

    def udt_send(self, dst_addr, data_S, mtuMAX):
        if len(data_S) > mtuMAX:
            part1, part2 = data_S[0:int(len(data_S) / 2)], data_S[int(len(data_S) / 2):]

            packet1 = NetworkPacket(dst_addr, part1)

            self.out_intf_L[0].put(packet1.to_byte_S())  # send packets always enqueued successfully
            print('%s: sending packet "%s" out interface with mtu=%d' % (self, packet1, self.out_intf_L[0].mtu))

            packet2 = NetworkPacket(dst_addr, part2)
            self.out_intf_L[0].put(packet2.to_byte_S())  # send packets always enqueued successfully
            print('%s: sending packet "%s" out interface with mtu=%d' % (self, packet2, self.out_intf_L[0].mtu))
        else:
            p = NetworkPacket(dst_addr, data_S)
            self.out_intf_L[0].put(p.to_byte_S())  # send packets always enqueued successfully
            print('%s: sending packet "%s" out interface with mtu=%d' % (self, p, self.out_intf_L[0].mtu))

    ## receive packet from the network layer
    segment_buffer = []  # to hold the segments that we create

    def udt_receive(self):
        pkt_S = self.in_intf_L[0].get()
        if pkt_S is not None:
            self.segment_buffer.append(pkt_S[NetworkPacket.header_length:])  # add/ append to the buffer
            if not NetworkPacket.is_segment(pkt_S):
                print('%s: received packet "%s"' % (self, ''.join(self.segment_buffer)))
                self.segment_buffer.clear()

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


## Implements a multi-interface router described in class
class Router:

    ##@param name: friendly router name for debugging
    # @param intf_count: the number of input and output interfaces
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_count, max_queue_size):
        self.stop = False  # for thread termination
        self.name = name
        # create a list of interfaces
        self.in_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]
        self.out_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]

    ## called when printing the object
    def __str__(self):
        return 'Router_%s' % (self.name)

    ## look through the content of incoming interfaces and forward to
    # appropriate outgoing interfaces

    def forward(self):
        mtuValue = self.out_intf_L[0].mtu  # mtu for link from routera to server/end host this should = 30
        for i in range(len(self.in_intf_L)):
            pkt_S = None
            try:
                # get packet from interface i
                pkt_S = self.in_intf_L[i].get()
                # if there is a packet make a forwarding decision
                if pkt_S is not None:
                    # from one packet to many segmented packets
                    packets = NetworkPacket.from_byte_S(pkt_S, mtuValue)  # parse packets out

                    # HERE you will need to implement a lookup into the
                    # forwarding table to find the appropriate outgoing interface
                    # for now we assume the outgoing interface is also i

                    for p in packets:  # for all of the segments
                        self.out_intf_L[i].put(p.to_byte_SSegment(), True)
                        print('%s: forwarding packet "%s" from interface %d to %d with mtu %d'
                              % (self, p, i, i, self.out_intf_L[i].mtu))
            except queue.Full:
                print('%s: packet "%s" lost on interface %d' % (self, p, i))
                pass

    ## thread target for the host to keep forwarding data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            self.forward()
            if self.stop:
                print(threading.currentThread().getName() + ': Ending')
                return
