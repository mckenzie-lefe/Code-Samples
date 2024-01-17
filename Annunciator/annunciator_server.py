import logging
import socket as s
import time
import threading
import configparser
from datetime import timedelta, datetime as dt
from helpers import * 
from led_sign_client import LEDSignClient
from intercom_client import IntercomClient
from annunciator import Annunciator
import dcs_data_pb2
from globals import *

class AnnunciatorServer:
    # socket communication constants ------------------------------------------
    nak_resp = 'NAK'.encode()
    ack_resp = 'ACK'.encode()
    power_cycle_resp = 'POWERCYCLE'.encode()
    busy_resp = 'BUSY'.encode()
    alert_resp = 'ALERT'.encode()
    no_timer_resp = 'NO-TIMER'.encode()
    done_resp = 'DONE'.encode()

    def __init__(self):
        self.power_cycling = False
        self.processing_custom_msg = False
        self.dcs_sock = None
        self.lock = threading.Lock()    # used to set 'processing_custom_msg'
        self._init_config()
        self.annunciator = Annunciator()

        if not exit.is_set():
            LOGGER.info("Starting DCS update loop ...")
            threading.Thread(target=self.dcs_update).start()

            LOGGER.info("Starting listening loop...")
            self.listen_on_socket()         # start website listening loop

        self.annunciator.stop()     # exit

    def _init_config(self):
        """ Sets attriubtes using values found in annunciator_config.ini """
        LOGGER.info('Retrieving values from annunciator_config.ini')
        try:
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)

            # Communicating with app 
            self.host = config.get("SERVER", "HOST")    
            self.port = config.getint("SERVER", "PORT")
            self.panel_tag = config.get("SERVER", "PANEL")

            # Communicating with DCS link
            self.dcs_host = config.get("DCS", "HOST")
            self.dcs_port = config.getint("DCS", "PORT")

            debug = config.getboolean("SETTINGS", "DEBUG")
            if debug:
                logging.root.setLevel(logging.DEBUG)
            else:
                logging.root.setLevel(logging.INFO)

        except Exception as exc:
            LOGGER.error('Error retierving data from annunciator_config.ini. '
                             + str(exc))

    def _create_socket(self, ip, port):
        """ Reliably creates a TCP/IP socket at the specified port. 

        :return: A connected socket object if successfull, or None
            if exit has been set.
        """
        assert type(ip) == str
        attempt = 1

        while not exit.is_set():  
            sock = s.socket(s.AF_INET, s.SOCK_STREAM)
            sock.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR, 1)

            try:
                sock.bind((ip, port))
                sock.settimeout(5)
                sock.listen()
                LOGGER.info(f'Server listening on {ip}:{port}')
                return sock

            except Exception as exc:
                attempt += 1
                LOGGER.error(f'Failed to create socket ({attempt}): {exc}')
                exit.wait(60)   # wait 1 min
                if attempt > 5:
                    exit.wait(900)   # wait 15 min
        return None

    def _client_send(self, sock, client_code, msg):
        """Sends message with appropriate suffix for client over socket.
        All messages sent to appserver must end with \n as client program is
        written in java and uses read line 

        :param sock: connected socket object
        :param client_code: a single character representing the code for 
            the type of client on the connected socket 
        :param msg: bytes object of message content to send over socket
        :raises InvalidParameter: if client code not recongized
        """
        if client_code == 'A':      # webserver 
            sock.sendall(msg)
        elif client_code == 'B':    # appserver
            sock.sendall(msg + b'\n')
        else:
            raise InvalidParameter()

    def _dcs_send(self, msg):
        """First Sends the number of bytes in msg padded to 4 bytes, then sends
        provided data across the given socket.

        :param msg:  A string containing the data to send.
        :return: True if all data successfully sent over sock, otherwise False

        """
        assert type(self.dcs_sock) == s.socket
        assert type(msg) == bytes

        msg_len = len(msg).to_bytes(4, 'big') # int to bytes

        try:
            self.dcs_sock.sendall(msg_len)
            self.dcs_sock.sendall(msg)

        except Exception as exc:
            LOGGER.error(f'Error sending {msg_len}: {exc}')
            self.dcs_sock.close()
            return False

        return True

    def _dcs_receive(self):
        """Receives 4 bytes of data indicating length of incomming message then 
        receives message and parses as Response message.

        :return: A Response message parsed from the received data or 
        None if an error occured.
        """
        assert type(self.dcs_sock) == s.socket

        try:
            content_length = self.dcs_sock.recv(4)

            data = self.dcs_sock.recv(int.from_bytes(content_length, 'big'))
            msg = dcs_data_pb2.Response()
            msg.ParseFromString(data)
            #print(f'DCS Received {msg}')
            return msg

        except:
            return None

    def _get_drums_content_msg(self):
        """Create encoded message containing drum stages to be sent over 
        socket."""
        #LOGGER.debug(f'DRUM STAGES: {msg}')
        msg = ""
        for drum in self.annunciator.drum_states:
            if drum['timer'].type != NO_TIMER:
                msg = msg + str(drum['timer'].type) + \
                    ','+ str(drum['timer'].start) + \
                    ',' + str(drum['timer'].duration) + \
                    ',' + str(drum['timer'].details) + '_'
            else:
                msg = msg + str(drum['stage']) + '_'

        #print(f'drums msg: {msg}')
        return msg[:-1].encode()

    def dcs_update(self):
        """
        Will display DCS down notification if dcs link is unreachable and the 
        current display is not a custom message or notification.

        If the response from the DCS link holds a notification and all new 
        stages for all of the drums, it will take awhile to process it all. 
        Since the DCS link needs to know if the notification was successfully 
        displayed a response with the results of processing the data needs to 
        be sent to the DCS link. Therefore the socket timeout is set to 80.
        """
        dcs_exc = 0
        msg = dcs_data_pb2.ClientMsg()

        while not exit.is_set():
            if self.power_cycling:
                time.sleep(5)
                continue

            try:
                self.dcs_sock = s.socket(s.AF_INET, s.SOCK_STREAM)
                self.dcs_sock.settimeout(5)
                self.dcs_sock.connect((self.dcs_host, self.dcs_port))
                
                msg.msg = dcs_data_pb2.ClientMsg.MsgType.DATA_REQUEST

                if self._dcs_send(msg.SerializeToString()):

                    resp = self._dcs_receive()
                    self.dcs_sock.settimeout(80) 

                    # NAK until proven otherwise
                    msg.msg = dcs_data_pb2.ClientMsg.MsgType.NAK  
                    
                    if resp is not None and resp.is_valid:
                        try:
                            self.annunciator.check_alarms(resp.alarms) 

                            if ( resp.notify.code != 'NNN' and 
                                    self.annunciator._has_priority('notify') ):
                                self.annunciator.display_notify(resp.notify)
                                msg.recieved_notify = resp.notify.code

                            time.sleep(.5)  # allow time for other threads to run
                            self.annunciator.update_drum_states(resp.drums) 
                            self.annunciator.display_drums()

                            msg.msg = dcs_data_pb2.ClientMsg.MsgType.ACK 

                        except SignError:
                            msg.msg = dcs_data_pb2.ClientMsg.MsgType.NAK
                            self._dcs_send(msg.SerializeToString())
                            self.dcs_sock.close()

                            self.power_cycling = True
                            self.annunciator.power_cycle()
                            self.power_cycling = False
                            continue

                        except InvalidParameter as exc:
                            # invalid/missing values in resp.alarms
                            LOGGER.error(f'invalid param')
                            exit.wait(3)   # total of 5 seconds 

                    if self._dcs_send(msg.SerializeToString()):
                        self.dcs_sock.close()
                    dcs_exc = 0

            except TimeoutError:
                if dcs_exc % 15 == 0:
                    LOGGER.error('Socket to DCS link timeout.'
                                        ' Check network connection.')
                dcs_exc += 1

            except ConnectionRefusedError:
                if dcs_exc == 20 or dcs_exc % 400 == 0: # every 20mins
                    LOGGER.error('DCS Server is down' 
                                    ', unable to make connection.')
                dcs_exc += 1  

            except ConnectionResetError:
                LOGGER.error('Error connection reset by peer.')

            except Exception as exc:
                if dcs_exc % 15 == 0:
                    LOGGER.error(f'Error in dcs_update() - {exc}')   
                dcs_exc += 1

            msg.Clear() 
            
            if dcs_exc > 20:
                self.annunciator.display_dcs_down()

            exit.wait(3)   # time between updates

    def handle_connection(self, s, a):
        """ SOCKET COMMUNICATION PROTOCOL
            -----------------------------
            CASE 1
                receive: client code + 1          (display custom message cmd)
                send: 'ACK'
                receive: message length
                receive: message
                send: ['ACK', 'NAK', BUSY', 'ALERT']
            CASE 2
                receive: client code + 1          (display custom message cmd)
                send: 'BUSY'
            CASE 3
                receive: client code + 2          (display drums)
                send: 'ACK'

            CASE 4
                receive: client code + 3          (request current display cmd)
                send: current display code
                send: [drum_stage, current_msg]
            CASE 5 
                receive: any
                send: 'POWERCYCLE'
            CASE 6
                receive: anything other than 1 or 2
                send: 'NAK'
        
        Will only allow for one thread at a time to process a display custom 
        message request. The thread that is able to set 'processing_custom_msg'
        to True is allowed to process request. 
        This is needed to handle receiving multiple display custom message 
        request at the same time. 
        If a notification is playing self.display_custom_msg waits for it to 
        finish before processing request.        
        """
        try:
            cmd = s.recv(2).decode()
            c = cmd[0]  # client code (A or B)
            cmd_code = cmd[1]
            
            if self.power_cycling:
                self._client_send(s, c, self.power_cycle_resp)
                LOGGER.debug(f'Sent POWERCYCLE to {c}-conn: {a}')
                return

            # display custom message
            if '1' in cmd_code:
                with self.lock:
                    if not self.processing_custom_msg:
                        self.processing_custom_msg = True
                    else:
                        LOGGER.info('BUSY')
                        self._client_send(s, c, self.busy_resp)
                        return
                try:
                    LOGGER.info('Update custom message command from webserver')
                    self._client_send(s, c, self.ack_resp)

                    msg_len = s.recv(3).decode()      
                    cmd = s.recv(int(msg_len)).decode()
                    # cmd = <msg_type><dur_code><msg_text>
                    LOGGER.debug(f'cmd: {cmd}') 

                    # update LED sign
                    try: 
                        if self.annunciator.display_custom_msg(
                            cmd[0], 
                            dur_code_to_wait_time(cmd[1]), 
                            cmd[2:]
                        ):
                            self._client_send(s, c, self.ack_resp)
                        else:
                            self._client_send(s, c, self.nak_resp)

                    except SignLeaseError:
                        LOGGER.warning('BUSY - SignLeaseError in' 
                                        'display_custom_msg()')
                        self._client_send(s, c, self.busy_resp)

                except Exception as exc:
                    LOGGER.warning(f'Error handling custom msg request {exc}')

                with self.lock:
                    self.processing_custom_msg = False

            # display drums
            elif '2' in cmd_code:
                LOGGER.info('Handling set display to drums request ...')
                if self.annunciator.current_display == ALERT_DISPLAY:
                    self._client_send(s, c, self.alert_resp)
                else:
                    try:
                        self.annunciator.display_drums(override=True)
                        self._client_send(s, c, self.ack_resp)

                    except SignLeaseError:
                        LOGGER.warning('BUSY - SignLeaseError in'
                                       'set_display drums')
                        self._client_send(s, c, self.busy_resp)

                    except SignError:
                        self._client_send(s, c, self.nak_resp)

            # request current display
            elif '3' in cmd_code:
                self._client_send(s, c, str(self.annunciator.current_display).encode())

                if self.annunciator.current_display == DRUMS_DISPLAY:
                    self._client_send(s, c, self._get_drums_content_msg())
                    
                else:    # custom message, notify or alert
                    #LOGGER.debug(f'current_msg: {self.current_msg}')
                    self._client_send(s, c, self.annunciator.current_msg.encode())
                    if c == 'B':
                        self._client_send(s, c, self.done_resp)

            else:
                LOGGER.error(f'Invalid command code from client: {cmd_code}')
                self._client_send(s, c, self.nak_resp)
                return

        except Exception as exc:
            LOGGER.error(f'Error receiving data in handle_connection - {exc}')

    def listen_on_socket(self):
        """
        _create_socket() will only returns if able to create sock or exit is set
        """
        sock = self._create_socket(self.host, self.port)  

        while not exit.is_set():
            try:
                conn, addr = sock.accept()
                threading.Thread(target=self.handle_connection, 
                                    args=(conn, addr), daemon=True).start()
                
            except s.timeout:
                pass

            except Exception as exc:
                LOGGER.error(f'Exc occurred: {exc}. Restarting listening socket')
                sock.close()
                sock = self._create_socket(self.host, self.port)

            time.sleep(.5)  # allow time for other threads to run

        # END WHILE -----------------------------------------------------------

        if sock:
            sock.close()
        
        LOGGER.info('Exiting website listening method ...')


# ------------------------------------------------------------------------------

if __name__ == '__main__':
    annunc = AnnunciatorServer()