import socket
import time
import hashlib
from threading import Thread


class UdpConnection:
    def __init__(self, sock, hostname, port, timeout):
        self.socket = sock
        self.hostname = hostname
        self.port = port
        self.socket.settimeout(timeout)
        self.myTuple = (hostname, int(port))
        self.socket.connect(self.myTuple)

    def send(self, message):
        message = "{}\n".format(message)
        data = message.encode("UTF-8")
        checksum = hashlib.md5(data)
        message = message + str(checksum.digest())
        self.socket.send("{}\n".format(message).encode("UTF-8"))

    def receiveFromServer(self, buffer):
        try:
            data = self.socket.recv(buffer)
            return data.decode("UTF-8")
        except socket.timeout:
            return None

    def receive(self, buffer):
        try:
            data = self.socket.recv(buffer)
            data = data.decode("UTF-8")
            message = data.split("\n", 1)[0]
            checksum = data.split("\n", 1)[1]
            if checksum is not '':
                correct = self.verify_checksum(message, checksum)
            else:
                correct = True
            if correct:
                return message
        except socket.timeout:
            return None

    def verify_checksum(self, message, checksum):
        correct = False
        data = message.encode("UTF-8")
        if hashlib.md5(data).digest() == checksum:
            correct = True

        return correct


class User:
    def __init__(self, name, udpConn):
        self.name = name
        self.udpConn = udpConn
        self.connected = True
        self.messages = []
        self.count = 0
        self.send = False
        self.ack = False


def represents_positive_int(s):
    try:
        return int(s)
    except ValueError:
        return -1


def create_udp_socket(timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # hostname = input("Specify the hostname (IP address): ")
    # port = input("Specify the port number: ")
    hostname = '3.121.226.198'
    port = 5382
    while represents_positive_int(port) < 0:
        port = input("Port number should be a positive integer. Try again: ")
    return UdpConnection(sock, hostname, port, timeout)


def try_create_new_user(udpConn: UdpConnection, name):
    udpConn.send("HELLO-FROM {}".format(name))
    data = udpConn.receiveFromServer(2048)
    while True:
        if data is None:
            print("Something is wrong with the connection")
        elif data.startswith("HELLO {}".format(name)):
            print("User created!")
            return User(name, udpConn)
        elif data.startswith("IN-USE"):
            print("This username is already in use\n")
        elif data.startswith("BUSY"):
            print("Server is to busy, try again later\n")
        retry = input("No acknowledgement... Try again? (Y/N)")
        if retry.lower() == "y":
            try_create_new_user(udpConn, name)
            return User(name, udpConn)
        else:
            return None


def handle_user_input(user: User):
    while user.connected:
        line = input("Command: ")
        line = line.split()
        message = ''
        if len(line) == 0:
            continue
        elif line[0] == "!quit":
            user.connected = False
            break
        elif line[0] == "!who":
            message = "WHO"
            user.ack = True
        elif line[0].startswith('@'):
            target = line[0][1:]
            message = ' '.join(line[1:])
            message = "SEND {} {}".format(target, message)
        elif line[0].startswith('set'):
            line = [x.upper() for x in line]
            message = ' '.join(line)

        if message != "WHO":
            message = message + ' ' + str(user.count)
        user.count += 1

        user.udpConn.send(message)
        user.messages.append(message)
        user.send = True
        while user.send:
            time.sleep(1)  # Sleep
            if not user.ack:
                user.udpConn.send(message)
            elif not message.startswith("SEND"):
                break
        user.ack = False
        user.send = False


def handle_server_input(user):
    while user.connected:
        line = user.udpConn.receive(2048)
        if line is not None:
            line = line.split()
            if line[-1] == "SEND-OK":
                 user.ack = True
                 user.send = False
            elif len(line) == 0:
                user.connected = False
                break
            elif line[0] == "DELIVERY":
                if len(line) == 1:
                    continue
                name = line[1]
                seqNum = line[-1]
                line.pop()
                if int(seqNum) < user.count:
                    message = "RESEND {}".format(user.count)
                    user.udpConn.send(message)
                    continue
                message = ' '.join(line[2:])
                print(name, "says:", message)
            elif line[0] == "WHO-OK":
                users = ", ".join(line[1:])
                print("Online users:", users)
            elif line[0] == "RESEND":
                number = line[1]
                message = user.messages[number]
                user.udpConn.send(message)


def handle_new_user(user):
    user_t = Thread(target=handle_user_input, args=(user,))
    server_t = Thread(target=handle_server_input, args=(user,))
    user_t.start()
    server_t.start()
    user_t.join()
    server_t.join()


if __name__ == "__main__":
    udpConn = create_udp_socket(1)
    name = input("Specify a username: ")
    user = try_create_new_user(udpConn, name)
    if user is not None:
        handle_new_user(user)
    print("Closing the connection")
    udpConn.socket.close()