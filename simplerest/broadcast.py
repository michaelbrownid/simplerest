import socket
import argparse
import requests

class sender:
    def __init__(self, inport, inserverport):
        print "sender init %d serverport %d" % (inport,inserverport)
        self.serverport=inserverport
        self.UDP_IP_ADDRESS = "255.255.255.255" # broadcast local network
        self.Message = "%d,isanyoneoutthere" % inserverport
        self.port = inport
        self.mysock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.mysock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def send(self):
        print "sender.send"
        self.mysock.sendto(self.Message, (self.UDP_IP_ADDRESS, self.port))

class receiver:
    def __init__(self, inport):
        print "receiver init %d" % inport
        self.UDP_IP_ADDRESS = "" # default address
        self.port = inport
        self.mySock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.mySock.bind((self.UDP_IP_ADDRESS, self.port))

    def listen(self):
        print "receiver.listen"
        if True:
            data, addr = self.mySock.recvfrom(16)
            print "got data: ", data, "from addr:", addr
            (serveraddr,rest) = data.split(",",2)
            print "GOT BROADCAST"
            print "server: http://%s:%s/"  % (addr[0],serveraddr)
            url = "http://%s:%s/setkey?key=broadcast&value=0'" % (addr[0],serveraddr)
            print "turning off broadcast: curl '%s'" % url
            requests.get(url)

################################
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', help='the port to listen on for broadcasting servers', default=6789)
    parser.add_argument('--serverport', help='the parent server port that is listening', default=8080)
    args = parser.parse_args()

    myrec = receiver(args.port)
    myrec.listen()
