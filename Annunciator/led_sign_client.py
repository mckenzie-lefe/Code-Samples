import logging
import time
import serial
from led_sign_command import LEDSignCommand
from helpers import * 
from globals import *

LOGGER = logging.getLogger(__name__)

class LEDSignClient:
    """
    Variable files are for frequently changing information, as the sign will 
    not restart when it receives a variable file.

    Text files can embed variable, gif, png, bmp or other test files. When the
    sign receives a text file the sign will reset before displaying it.

    Values stored in indecs 0-5 in self.drum_stage, stage_var_files, 
    timer_var_files and new_stage corresponde the follow drums,
        0 = 1A,     1 = 1B,     2 = 2A,     3 = 2B,     4 = 3A,     5 = 3B

    """
    def __init__(self, serial_port, sign_addr, sent_attempts):
        self.serial_port = serial_port
        self.sent_attempts = sent_attempts
        self.sign_cmd = LEDSignCommand(sign_addr)

        self.sign_busy = True
        self._init_sign()
        self.sign_busy = False

    def _init_sign(self):
        self.set_stage(0, UNSET_STAGE)
        self.set_stage(1, UNSET_STAGE)
        self.set_stage(2, UNSET_STAGE)
        self.set_stage(3, UNSET_STAGE)
        self.set_stage(4, UNSET_STAGE)
        self.set_stage(5, UNSET_STAGE)
        self.set_display('drums')

    def _get_sign_datetime(self):
        self.sign_cmd.read_date()
        d = self.send_to_sign(read_dt=True)

        self.sign_cmd.read_time()
        t = self.send_to_sign(read_dt=True)

        return d+t

    def send_to_sign(self, cmd=None, read_dt=False):
        """ Sends command to Led sign over serial port. Command format outlined
        in MCS Protocol v3.2.doc

        PARAM
        cmd     optional command string. If this parameter is unset command
                in 'self.sign_cmd.cmd' is sent to sign.

        A thearding lock is required

        Returns true if message was successfully sent to sign and sign response
        was "ok". If "ok" is not received after command is sent, resends command
        up to four times. If after four attempts none were successful then false
        is returned.

        The multiple attempts to send the command is to identify if the sign
        requires a power cycle. Every once and in while the sign will not
        respond to the odd command or two. In which case the command will get
        through in the four attempts. If this is not the case the sign will not
        respond to any commands until it has been power cycled.
        """
        received = False
        attempts = 1
        dt = ""

        if cmd is None:
            cmd = self.sign_cmd.cmd.encode()

        while not received and attempts < self.sent_attempts:
            try:
                ser = serial.Serial(self.serial_port, 9600, timeout=3)
            except Exception as exc:
                LOGGER.error('error opening serial port.\n' +str(exc))
                raise SignError('Unable to open serial port')

            try:
                while len(cmd) > 1000:
                    ser.write(cmd[:1000])
                    cmd = cmd[1000:]

                if len(cmd) <= 1000:
                    LOGGER.debug(fill(str(cmd.decode()), 80))
                    ser.write(cmd)

                r = ser.read(2000)
                r = r.decode()

                time.sleep(1)

                if 'ok' in r:
                    received = True

                if read_dt:
                    prefix = len(cmd.decode()[:-2])
                    dt = r[prefix: -8]
                    #dt_str = dt[:2] + "-" + dt[2:4] + "-" +dt[4:8] #+ " ["+ dt[9:11] + ":"+ dt[11:13] + ":"+ dt[13:15] + "]"
                    #print(dt_str)

                ser.close()

                if not received:
                    time.sleep(2)
                    LOGGER.debug('response: ' + r)
                    if r is None or r == '':
                        LOGGER.warning('Sign did not respond on attempt' +
                                    str(attempts)+ '. Trying again..')
                        attempts = attempts + 1

            except Exception as exc:
                LOGGER.error('error sending ' +str(self.sign_cmd.cmd)+
                             ' over serial port.\n ' +str(exc))
                if ser:
                    ser.close()

        if not received:
            raise SignError()
        
        if read_dt:
            return dt

    def reset_sign(self):
        self.sign_cmd.reset_sign()
        self.send_to_sign()     

    def set_iso_timer(self, drum, dur, iso_valve):
        """
        Must get dt_str first as it is needed for command that sets the the
        timer variable file. It will mess up the command if called between  
        self.sign_cmd.start_cmd() & self.send_to_sign() 
        
        :param code: drum name or integer of drums code/pos in lists
        :param dur: timedelta of time left in isolation valve timer.
        :param iso_valve: tag name of isolation valve to close after countdown
        :raise SignError: if unable to reach sign 
        """
        assert type(iso_valve) == str
        
        LOGGER.debug(f'Timer set for {dur.seconds} seconds on drum {drum}')

        dt_str = self._get_sign_datetime()

        self.sign_cmd.start_cmd()
        self.sign_cmd.write_to_var(get_drum_state_file(drum))
        self.sign_cmd.set_font(TIMER_FONT)
        self.sign_cmd.set_color('white')
        self.sign_cmd.set_text('close')
        self.sign_cmd.add_new_line()
        self.sign_cmd.set_text(iso_valve+ ' ')
        self.sign_cmd.set_color('red')
        self.sign_cmd.add_countdown(dt_str=dt_str, secs=dur.seconds)
        self.sign_cmd.end_cmd()
        self.send_to_sign() 

    def set_timer(self, name, drum, dur, details):
        if name == ISO_TIMER:
            self.set_iso_timer(drum, dur, details)
        else:
            pass    #### ADD TIMERS here ####    

    def set_stage(self, drum, stage):
        self.sign_cmd.start_cmd()
        self.sign_cmd.write_to_var(get_drum_state_file(drum))
        self.sign_cmd.set_font(STAGE_FONT)
        self.sign_cmd.set_text_alignment('cb')
        self.sign_cmd.set_color(get_stage_color(stage))
        self.sign_cmd.set_text(get_stage_name(stage))   
        self.sign_cmd.end_cmd()
        self.send_to_sign()

    def update_variable_file(self, msg, file_name):
        """Updates the message variable file that is embeded in notify.txt, 
        danger.txt, warning.txt and info.txt. 

        variable file_name will be the same as corresponding display name

        It follows that changes to msg.var will cause changes to display when 
        notify.sh, danger.sh, warning.sh or info.sh are playing.

        If unsuccessful in updating SignError() raised.

        Returns True if custom message variable file was successfully updated,
        otherwise false. """
        lines = msg.split('\n')

        self.sign_cmd.start_cmd()
        self.sign_cmd.write_to_var(file_name)

        self.sign_cmd.set_text(lines[0])
        # handle newline characters in message
        for i in range(1, len(lines)):
            self.sign_cmd.add_new_line()
            self.sign_cmd.set_text(lines[i])

        self.sign_cmd.end_cmd()
        self.send_to_sign() 

    def update_alert_msg(self, txt, deck):
        '''Updates signs alarm and deck variable files.
            
        raises SignError() if sign does not respond

        PARAMETERS
        ==========
        txt: A string containing a list of active alarms. 
            Assumptions: 
                1. Alarms listed in 'txt' are seperated by a comma execpt  
                    for last listed alarm that should be seperated with '&'. 
                2. 'txt' will always end with a space.  
                    e.g 'H2S, LEL & FIRE '
        deck: A string containing the deck code for the locations of the 
                alarms in txt.

        RETURNS
        =======      
        If update successful, returns the string of the alert message being 
        displayed on the sign. Otherwise if invalid  deck code recevied, 
        returns and empty string.
        '''
        if deck not in [BOTH_DECKS, SWITCH_DECK, CUT_DECK]:
            LOGGER.error(f'Invalid deck recevied in update_alert_msg() {deck}')
            return ""
        
        self.sign_cmd.start_cmd()
        self.sign_cmd.write_to_var('alarm') 
        self.sign_cmd.set_color('white')
        self.sign_cmd.set_text(txt)
        self.sign_cmd.end_cmd()
        self.send_to_sign()

        msg = txt + 'detected on '
        if deck == BOTH_DECKS:
            txt = 'SWITCH & CUT'
        elif deck == SWITCH_DECK:
            txt = 'SWITCH'
        elif deck == CUT_DECK:
            txt = 'CUT'

        self.sign_cmd.start_cmd()
        self.sign_cmd.write_to_var('deck')
        self.sign_cmd.set_text(txt)
        self.sign_cmd.end_cmd()
        self.send_to_sign()

        return msg + txt + ' deck'

    def set_display(self, display_, msg="", decks="", update_script=True):
        """ Updates the necessary variable files and script file playing on 
        the sign. An error display is handled as notify display by sign.
        If display is 'drums and update_script if False, does nothing.

        Varibale file name will match display name

        :param display: display type to set sign as (int or string)
        :parma msg: text for variable file of display 
        :param decks: deck code of alarms for alert display
        :param update_script: boolean indicating to reset sign and change script 
        :return: msg if successfull otherwise raises SignError if sign is not 
            responding 
        """
        
        if type(display_) == int:   # ensure display name used
            display = get_display_name(display_)
        else:
            display= display_

        if display == 'error':  # treat error as notify
            display = 'notify'
        
        if display in ['info', 'danger', 'warning', 'notify']:
            self.update_variable_file(msg, file_name=display)
        elif display == 'alert':
            msg = self.update_alert_msg(msg, decks)

        # only need to play script if not already playing
        if update_script:
            self.reset_sign()   # stop playing current script
            self.sign_cmd.play_script(display)
            self.send_to_sign()  # raises SignError() on fail

        return msg
    
    def get_sign_lease(self):
        """Return true is successful obtained sign lease, otherwise false"""
        # wait for sign not to be busy
        for _ in range(5):
            if not self.sign_busy:
                self.sign_busy = True 
                return True
            time.sleep(4)

        raise SignLeaseError()    

    def return_sign_lease(self):
        self.sign_busy = False

