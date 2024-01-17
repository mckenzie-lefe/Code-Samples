import logging
import socket
import time
from datetime import timedelta, datetime as dt
import threading
from smbus import SMBus
from helpers import * 
from globals import *

LOGGER = logging.getLogger(__name__)

class IntercomClient:
    """
    OUTPUT BITS (sent to control panel to set lights on intercom)
        1A = 0, 1B = 1, 2A = 2, 2B = 3, 3A = 4, 3B = 5, 
        PC/UPS = 6, tigger power cycle = 7

    """
    def __init__(self, ts_host, ts_port, panel_tag):
        self.ts_host = ts_host
        self.ts_port = ts_port
        self.exit_flag = False
        self.panel_tag = panel_tag
        self.bus = SMBus(0)

        self.light_bits = [1, 1, 1, 1, 1, 1, 0, 0]  # 8 bits in a byte
        self.input_bits = None

        self.pc_notify = False
        self.ups_notify = False

        self.last_msg_played = ''
        self.time_of_last_msg = dt.now()
        # used to prevent queue backup from repeated button pushes
        self.time_of_last_repeat = dt.now()
        self.press_count = 0
        
        self.easter_egg_1 = '    \x1bp\"yababy.wav\"\r\n'
        self.easter_egg_2 = '    \x1bp\"ship1.wav\"\r\n'

        self.bus.write_byte_data(34, 3, bin_to_dec(self.light_bits))

        # start thread to listen for alarms and repeat button
        threading.Thread(target=self.run).start()

    def stop(self):
        self.exit_flag = True

    def run(self):
        """
            Input from control panel is one byte, whose bits indicate if an
            alarm is on. Bit values are stored in 'self.input_bits'
                bit 6   pc alarm    0 = on, 1 = off
                bit 7   ups alarm   0 = on, 1 = off

            The annunciator reads in one byte, whose bits indicate which lights
            to turn on. If the input from the control panel has an alarm bit set
            we need to tell the corresponding light on the annunciator to turn
            on. 'self.light_bits' is set according to input from the control
            panel then sent to the annunciator.
            There are 6 lights on the intercom which corresponding to a
            drum. If one of these lights is set to red then it means the
            corresponding drum is in the cut stage, otherwise if the light
            is set to green it means the corresponding drum is not in the
            cut stage.
                There are 2 lights on the front of the control panel. One
            labeled UPS/PC alarm and the other labeled gas alarm. The gas 
            alarm light is not used. As we are using its bit to power cycle
            the sign. 
                            LIGHT             DRUM
                bit 0   top on intercom        1A       1 = green, 0 = red
                bit 1   second from top        1B       1 = green, 0 = red
                bit 2   third from top         2A       1 = green, 0 = red
                bit 3   fourth from top        2B       1 = green, 0 = red
                bit 4   second from bottom     3A       1 = green, 0 = red
                bit 5   second from bottom     3B       1 = green, 0 = red
                bit 6   labeled PC/UPS alarm   -        1 = on,  0 = off
                bit 7   labeled gas alarm      -        1 = power cycle

        If the gas alarm is on no announcement is made on the intercom because
        the control panel will have cut power to it.

        When sending a message to the intercom to be played the command must
        start with 5 space as these are cut off. The reason for this is unknown.
        """

        while not self.exit_flag:
            # read input byte from control panel
            b = self.control_panel_byte('read')
            self.input_bits = str(bin(b))[2:]

            # check PC and UPS alarm if both off turn light off
            if not self.is_alarm_on(PC_ALARM) and not self.is_alarm_on(UPS_ALARM):
                self.set_lights(PC_UPS_LIGHT_BIT, False)

            # handle UPS alarm on
            if self.is_alarm_on(UPS_ALARM):
                self.alarm_UPS()
            else:
                self.ups_notify = False

            # handle PC alarm on
            if self.is_alarm_on(PC_ALARM):
                self.alarm_PC()
            else:
                self.pc_notify = False

            # check if repeat button pressed
            if self.repeat_button_pressed():
                LOGGER.info('Repeat button pressed')

                # Only repeats message if message send within last 30 mins 
                if (dt.now() - self.time_of_last_msg < timedelta(minutes=30) and 
                    dt.now() - self.time_of_last_repeat > timedelta(seconds=30)):   
                    self.send_to_intercom(self.last_msg_played)
                    self.press_count = 0
                else:
                    # repeat button held for 5 seconds
                    if self.press_count == 5:
                        self.send_to_intercom(self.easter_egg_1)
                    # repeat button held for 6 seconds
                    elif self.press_count == 8:
                        self.send_to_intercom(self.easter_egg_2)

                    self.press_count = self.press_count + 1
                time.sleep(2)
            else:
                self.press_count = 0

            time.sleep(1)

        LOGGER.info('Exiting intercom server listening thread.')

    def control_panel_byte(self, comm='read'):
        lock = threading.Lock()
        lock.acquire()

        if comm == 'read':
            # read byte
            return self.bus.read_byte_data(34, 0)

        # write byte
        self.bus.write_byte_data(34, 3, bin_to_dec(self.light_bits))
        lock.release()

    def set_lights(self, light, on=True):
        if on:
            self.light_bits[light] = 1
        else:
            self.light_bits[light] = 0

        self.control_panel_byte('write')

    def update_light(self, drum_light, stage_code):
        ''' Sets light corresponding to drum on intercom to red if in cut 
        stage, green otherwise. drum_light is bit position to set to turn 
        on light of corresponding drum'''

        if stage_code == CUT_STAGE:
            # set light red
            self.set_lights(drum_light, False)

        else:
            # set light green
            self.set_lights(drum_light)

    def repeat_button_pressed(self):
        if self.input_bits[REPEAT] == '0':
            self.time_of_last_repeat = dt.now()
            return True
        return False

    def is_alarm_on(self, alarm):
        if self.input_bits[alarm] == '0':
            return True
        return False

    def alarm_PC(self):
        self.set_lights(PC_UPS_LIGHT_BIT)

        # check that alarm notification has not already played
        if not self.pc_notify:
            alert = "ATTENTION, PC Fault on panel 33-P N L" + self.panel_tag
            msg = '    \x1bp\"START2.WAV\"\r\n' + alert \
                  + '\r\n\x1bp\"START2.WAV\"\r\n' + alert \
                  + '\r\n\x1bp\"END.WAV\"\r\n'
            self.send_to_intercom(msg)
            time.sleep(2)
            self.pc_notify = True

    def alarm_UPS(self):
        self.set_lights(PC_UPS_LIGHT_BIT)

        # check that alarm notification has not already played
        if not self.ups_notify:
            alert = "ATTENTION, UPS ALARM on panel 33-P N L " + self.panel_tag
            msg = '    \x1bp\"START2.WAV\"\r\n' + alert \
                  + '\r\n\x1bp\"START2.WAV\"\r\n' + alert \
                  + '\r\n\x1bp\"END.WAV\"\r\n'
            self.send_to_intercom(msg)
            time.sleep(2)
            self.ups_notify = True

    def power_cycle(self):
        self.light_bits[POWER_CYCLE_BIT] = 1
        
        for _ in range(10):
            self.control_panel_byte('write')
        time.sleep(5)

        self.light_bits[POWER_CYCLE_BIT] = 0
        self.control_panel_byte('write')

    def send_to_intercom(self, msg):
        LOGGER.debug(fill(f'Sending \'{msg}\' to intercome...',80))
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.ts_host, self.ts_port))
                s.sendall(msg.encode())     
                return True
        except Exception as exc:
            LOGGER.error(
                fill(f'Exception occurred in send_to_intercom: {exc}', 80))
            return False

    def announce_message(self, msg_type, msg):
        if msg_type in ['danger', '1', '1\n']:
            self.last_msg_played = 'Danger. ' + msg
        elif msg_type in ['warning', '2', '2\n']:
            self.last_msg_played = 'Warning. ' + msg
        else:
            self.last_msg_played = msg

        self.last_msg_played = '    \x1bp\"TONE1.WAV\"' + self.last_msg_played \
                               + '\r\n\x1bp\"END.WAV\"'
        if self.send_to_intercom(self.last_msg_played):
            time.sleep(2)

        self.time_of_last_msg = dt.now()
    
    def cut_warning(self, drum):

        def warning_thread():
            msg = '    \x1bp\"START.WAV\" Drum ' + drum + ' will start cut ing'\
                + ' operaition in ten minutes. Please vacate the area.' \
                + '\r\n'

            self.send_to_intercom(msg)

            time.sleep(50)

            msg = '    " Repeat Drum ' + drum + ' will start cut ing'\
                + ' operaition in ten minutes. Please vacate the area.' \
                + '\r\n\x1bp\"END.WAV\"'
            self.send_to_intercom(msg)

        # ---------------------------------------------------------------------

        tr = threading.Thread(target=warning_thread)
        tr.start()
        
    def announce_stage(self, drum, stage_code):    
        msg = '    \x1bp\"START.WAV\"' + drum \
            + get_stage_ts_msg(stage_code) \
            + '\r\n\x1bp\"END.WAV\"'

        self.send_to_intercom(msg)

    def announce_timer(self, drum, dur, timer_type, details):
        if timer_type == ISO_TIMER:
            msg = 'Isolation valve ' + details + ' for drum ' + \
                drum_code_to_str(drum) + ' is allowed to close in approximately '
        else:
            msg = ""

        secs = dur.seconds % 60
        mins = int((dur.seconds - secs) / 60) + round(secs / 60)

        if mins == 1:
            m = str(mins) + ' minute'
        else:
            m = str(mins) + ' minutes'
        
        msg = '    \x1bp\"START.WAV\"' + msg + m + '\r\n\x1bp\"END.WAV\"'

        self.send_to_intercom(msg)

    def play_alert(self, msg):
        msg = '    \x1bp\"START.WAV\"' + msg + '\r\n'

        self.send_to_intercom(msg)
        