"""
http://uguu.ca/477/ping-in-pure-python/
ping
====
Provides a simple, efficient means of executing PINGs in pure, stdlib Python.
 
Legal
=====
This is free and unencumbered software released into the public domain.
 
Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.
 
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
 
Authors
=======
Neil Tallim <flan@uguu.ca>
"""
import array
import os
import select
import socket
import struct
import threading
import time
 
_ICMP_ECHO_REPLY = "\x00" #: The standard PONT ICMP identifier (0)
_ICMP_ECHO_REQUEST = "\x08" #: The standard PING ICMP identifier (8)
_ICMP_CODE = "\x00" #: Always 0 for PING/PONG
 
_PID = struct.pack('!H', os.getpid())
 
_SEQUENCE_LOCK = threading.Lock()
_SEQUENCE = -1
def _get_sequence_identifier():
    global _SEQUENCE
    with _SEQUENCE_LOCK:
        if _SEQUENCE == 65535: #Upper limit of 16-bit integer
            _SEQUENCE = -1
        _SEQUENCE += 1
        return struct.pack('!H', _SEQUENCE)
         
class Handler(object):
    """
    Provides a facility for sending and receiving PING messages.
    """
    _header_prefix = None #: The byte-string that makes up every header-prefix to be emitted.
    _header_prefix_checksum = None #: The byte-string that makes up every header to be checksummed.
    _timeout = None #: The number of seconds to wait for a response.
    _payload = None #: The payload to be sent with every packet.
     
    _sequence = None #: The current sequence-identifier.
    _header = None #: The current header, for error-recognition.
    _destination = None #: The address to PING.
    _destination_ip = None #: The IP to PING.
     
    _socket = None #: The socket to use for communication.
     
    def __init__(self, destination, timeout=5.0, payload_size=56):
        """
        Initialises a handler for potentially repeated use.
         
        :param str destination: The address to be PINGed.
        :param float timeout: The number of seconds to wait for a response.
        :param int payload_size: The number of bytes to use for the payload.
        """
        self._header_prefix = _ICMP_ECHO_REQUEST + _ICMP_CODE
        self._header_prefix_checksum = (
         self._header_prefix + "\x00\x00" + _PID
        )
        self._destination = destination
        self._timeout = timeout
        #Make the payload an ascending sequence of bytes.
        self._payload = ''.join(chr(i & 0xff) for i in xrange(payload_size))
         
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
         
    def close(self):
        """
        Immediately cleans up resources.
        """
        self._socket.close()
         
    def _checksum(self, suffix):
        """
        Computes the RFC1122 checksum of the checksum header and ``suffix``.
         
        :param str suffix: The variable data to be checksummed.
        :return int: The full packet's checksum.
        """
        data = self._header_prefix_checksum + suffix
        if len(data) & 1: #Odd
            checksum = sum(array.array('H', data[:-1]))
            checksum += ord(data[-1][-1]) << 8 #Add the final byte, shifted by one
        else: #Even
            checksum = sum(array.array('H', data))
        checksum = (checksum >> 16)  +  (checksum & 0xffff)
        checksum += (checksum >> 16)
        return (~checksum) & 0xffff
         
    def _receive(self):
        """
        Waits for a PONG.
         
        :return float: The time at which a response was received.
        :except socket.error: Something went wrong during communication.
        :except select.error: Something went wrong while waiting for a response.
        :except TimeoutError: An unexpected ICMP response was received.
        :except ValidationError: The received response was properly addressed,
            but corrupt.
        :except ICMPError: An unexpected ICMP response was received.
        """
        timeout = self._timeout
        while timeout > 0:
            start = time.time()
            active_sockets = select.select((self._socket,), (), (), timeout)[0]
            received = time.time()
            if not active_sockets:
                break
                 
            (data, source) = active_sockets[0].recvfrom(4096)
            if data[20] == _ICMP_ECHO_REPLY: #It could be a response to the ping
                if data[24:26] == _PID and data[26:28] == self._sequence:
                    if data[28:] == self._payload:
                        return received
                    raise ValidationError("Payload did not match expected value")
            else: #It's definitely not a ping response, so see if it's an error
                if data[-8:] == self._header: #It's an error in response to the PING
                    raise ICMPError(ord(data[20]), ord(data[21]))
            timeout -= time.time() - start
        raise TimeoutError("No PING response received")
         
    def _send(self):
        """
        Sends a PING.
         
        Side-effects: sets ``self._header``.
         
        :return float: The time at which the PING was sent.
        :except socket.error: Something went wrong during communication.
        """
        checksum = self._checksum(self._sequence + self._payload)
        self._header = self._header_prefix + struct.pack('<H', checksum) + _PID + self._sequence
        self._socket.sendto(self._header + self._payload, (self._destination_ip, 0))
        return time.time()
         
    def ping(self, requery_dns=False):
        """
        Sends a PING and provides RTT.
         
        Side-effects: sets ``self._destination_ip``, ``self._sequence``,
            ``self._header``.
         
        :param bool requery_dns: Whether the destination address should be
            re-requested from the system's resolver.
        :return float: The number of seconds required to receive a response.
        :except socket.error: Something went wrong during communication.
        :except select.error: Something went wrong while waiting for a response.
        :except TimeoutError: No response was received.
        :except ValidationError: The received response was properly addressed,
            but corrupt.
        :except ICMPError: An unexpected ICMP response was received.
        """
        if requery_dns or not self._destination_ip:
            self._destination_ip = socket.gethostbyname(self._destination)
             
        self._sequence = _get_sequence_identifier()
        start = self._send()
        return self._receive() - start
         
class PINGError(Exception): pass
class TimeoutError(PINGError): pass
class ValidationError(PINGError): pass
class ICMPError(PINGError):
    def __init__(self, type, code):
        self.type = type
        self.code = code
         
    def __str__(self):
        return "ICMP type=%(type)i, code=%(code)i" % {
         'type': self.type,
         'code': self.code,
        }