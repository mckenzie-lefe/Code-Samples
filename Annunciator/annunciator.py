import logging
import socket as s
import time
import threading
import configparser
from datetime import timedelta, datetime as dt
from helpers import * 
from led_sign_client import LEDSignClient
from intercom_client import IntercomClient
import dcs_data_pb2
from globals import *

class Annunciator:

    def __init__(self):
        self.bootup = True
        self.current_display = 0
        self.current_msg = "" 
        self.wait_id = 0
        self.dcs_down_msg = 'Drum cut cycle stages unknown. ' \
                                'Link to DCS server down.'

        self.alarms = { 
            'H2S': False, 
            'LEL': False, 
            'FIRE': False, 
            'deck': NO_DECK 
        }

        self._init_drum_states()
        self._init_config()

        LOGGER.info("Starting IntercomClient...")
        self.intercom = IntercomClient(self.ts_host, self.ts_port, 
                                        self.panel_tag)

        self._init_sign()

    def _init_config(self):
        """ Sets attriubtes using values found in annunciator_config.ini """
        LOGGER.info('Retrieving values from annunciator_config.ini')
        try:
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)

            self.panel_tag = config.get("SERVER", "PANEL")

            # serial port to talk to LED sign
            self.serial_port = config.get("LED SIGN", "SERIAL_PORT")
            self.sign_addr = config.get("LED SIGN", "address")
            self.max_send_attempts = config.getint("LED SIGN", "SEND_ATTEMPTS")

            # Communicating with speaker/ control panel
            self.ts_host = config.get("INTERCOM", "HOST")
            self.ts_port = config.getint("INTERCOM", "PORT")

            debug = config.getboolean("SETTINGS", "DEBUG")
            if debug:
                logging.root.setLevel(logging.DEBUG)
            else:
                logging.root.setLevel(logging.INFO)

        except Exception as exc:
            LOGGER.error('Error retierving data from annunciator_config.ini. '
                             + str(exc))

    def _init_drum_states(self):
        self.drum_states = []
        for _ in range(6):
            t = dcs_data_pb2.Timer()
            t.type = NO_TIMER
            self.drum_states.append({'stage': UNSET_STAGE, 'timer': t})
            t = None

    def _init_sign(self):
        LOGGER.info("Starting LEDSignClient...")
        self.sign = None
        while not exit.is_set():
            try:
                self.sign = LEDSignClient(self.serial_port, self.sign_addr, 
                                            self.max_send_attempts)
                break

            except SignError:
                if not exit.is_set():   
                    self.power_cycle()

            except Exception as exc:
                LOGGER.error(f'Error initalizing LEDSignClient {exc}')
                exit.set()
                return

    def _reset(self):
        ''' Turns off alarm flags and unsures that all drum cut cycle stages 
        are unset on sign.
        Assumed that drum['timers'] is always a Timer message and never None
        '''
        self.alarms['H2S'] = False
        self.alarms['LEL'] =  False
        self.alarms['FIRE'] = False

        self.sign.get_sign_lease()

        for t in self.sign.active_timers:
            self.sign.clear_timer(t)
            
        for idx, drum in enumerate(self.drum_states):
            drum['stage'] = UNSET_STAGE
            drum['timer'].type = NO_TIMER
            self.sign.update_drum_state(idx, get_stage_bmp(UNSET_STAGE))
            
        self.sign.return_sign_lease()

    def _has_priority(self, display):
        """Checks if a display type has priority over the current display type
            - drums has priority if current display is error.
            - Message displays have prioity if current display is NOT alert       
            - Error has prioity if current display is drums or alert 
                (Assumed that dcs_exc has been checked)
            - Alert always has proity

        :param display: interger or string representing a sign display type
        :return: True if parameter 'display' has prioity over the current 
            display, otherwise False.
        """
        display_name = get_display_name(display)

        if ((display_name == 'drums' and 
             self.current_display == ERROR_DISPLAY) or   
            (display_name == 'error' and 
             self.current_display in [DRUMS_DISPLAY, ALERT_DISPLAY]) or
            (display_name in ['danger', 'warning', 'info', 'notify', '1', '2', '3', '4'] and 
             self.current_display != ALERT_DISPLAY)):
            return True
            
        return False
 
    def _turn_on_alert(self, txt):
        """Sets sign to display alert message about active alarms.

        :param txt: string of active alarm names seperated by commas
        :raises SignError: if LED sign is unreachable
        """
        LOGGER.info('DETECTED ' + txt)
        try:
            self._set_display('alert', msg=txt)     
            self.intercom.play_alert(self.current_msg)

        except SignLeaseError:
            LOGGER.warning('Sign Lease Error in display_alert()')
        except SignError:
            raise SignError()
        except Exception as exc:
            # since not SignLeaseError can assume lease was not returned
            self.sign.return_sign_lease()
            LOGGER.error(f'Error in _turn_on_alert - {exc}')             

    def _turn_off_alert(self):
        """Reliably changes sign display from alert to drums
        
        :raises SignError: if LED sign is unreachable
        """
        while True:     # try until successfull
            try:
                self._set_display('drums') 
                break

            except SignLeaseError:
                continue    
            except SignError:
                LOGGER.error('Unable to stop displaying alert on sign.')
                raise SignError()
            except Exception as exc:
                LOGGER.error(f'Unable to stop displaying alert on sign. {exc}')
                self.power_cycle()  # ensure false alarm does not play
                
    def _set_timer_state(self, new_timer, drum):
        """Updates drum state if timer type has changed. This means either 
        clearing expired timer from display or

        If timer type is NO_TIMER, the data in the rest of the feilds are 
        garbage.

        Assumed drum_states[drum]['timer'] and new_timer.type are never None

        :param new_timer: Timer msg holding current timer data of drum from DCS
        :param drum: drum position in lists
        :returns: True if active timer, False otherwise.
        """
        if self.drum_states[drum]['timer'].type != new_timer.type:

            dur = timedelta(minutes=new_timer.duration) - (dt.now() - 
                dt.strptime(new_timer.start, "%Y-%m-%dT%H:%M:%S"))
            
            self.sign.set_iso_timer(new_timer.type, drum, dur, new_timer.details)
            LOGGER.info(f'{drum_code_to_str(drum)} timer set')      

            time.sleep(.5)  # allow time for other threads to run
            self.drum_states[drum]['timer'].CopyFrom(new_timer)
            self.intercom.announce_timer(drum, dur, 
                                         new_timer.type, new_timer.details)
        
    def _set_stage_state(self, new_stage, drum):
        """
        If self.bootup is true, or the new stage is unset, stage change will 
        not be announced. 
        """
        if self.drum_states[drum]['stage'] != new_stage:
            
            self.sign.set_stage(drum, new_stage)
            drum_name = drum_code_to_str(drum)

            if (self.drum_states[drum]['stage'] != UNSET_STAGE and 
                self.current_display == DRUMS_DISPLAY and
                not self.bootup):

                self.intercom.announce_stage(drum_name, new_stage)

            time.sleep(.5)  # allow time for other threads to run
            LOGGER.info(f'{drum_name} now in {get_stage_name(new_stage)}'
                        f' ({new_stage})')
                    
            self.drum_states[drum]['stage'] = new_stage
            self.intercom.update_light(drum, new_stage)
 
    def _set_display(self, display, msg=""):
        """Changes the current sign display. A sign lease is needed to call 
        self.sign.set_display()

        :param display: interger or string representing a sign display type
        :param msg: variable file content needed for message display types
        :raises SignError: if LED sign is unreachable
        :raises SignLeaseError: if unable to acquire sign lease to set display
        """

        def do_script_update(new: int):
            """Checks if a different script file needs to be played.

            :param new: sign display code of new display
            :return: False if 'new' is the same as the current display, 
                otherwise True. 
            """
            if new == self.current_display:
                return False
            return True

        #----------------------------------------------------------------------

        self.sign.get_sign_lease()      
        code = get_display_code(display)

        self.current_msg = self.sign.set_display(code, msg=msg, 
            decks=self.alarms['deck'], update_script=do_script_update(code))                           

        self.current_display = code
        self.sign.return_sign_lease()

    def stop(self):
        LOGGER.info('Exiting annunciator server.')
        if self.sign is not None:
            self.sign.reset_sign()
        if self.intercom is not None:
            self.intercom.stop()

    def display_custom_msg(self, msg_type, duration, msg):
        """ Announces a message by displaying it on the sign and sending it to 
        the intercom. Message will appear on sign for the given duration, if no 
        other message is recevied from the webserver and no alarms are recevied 
        from DCS. At the end of the duration, if the sign display has not changed, 
        will change the sign display to drums.

        Assumed that _has_priority() was called before display_custom_msg()

        :param msg_type: message display type code as string 
        :param duration: time to display message in seconds
        :param msg: message text to be displayed
        :raises SignLeaseError: if unable to acquire sign lease to set display

        If a notification is being displayed, will wait for it to finish before 
        displaying custom message. 
        Allows display to change to notifications received by DCS. If notification
        is playing when the end of the message duration is reached, will wait for 
        the notification to end before changing it to drums.  
        """
        def check_wait_id_reset():
            """Checks if wait ids needs to be reset, and resets as needed"""
            if self.wait_id == 30:
                self.wait_id = 0

        def wait_thread(dur, wid):
            """ Sleeps/waits for 'dur' amount of time. If wait has NOT been 
            canceled by the end of the wait, resets display to drums.

            NOTE: We do not need to recover from not being able to obtain a 
            sign lease to change the display. This is because it means that the 
            display is being changed thus also canceling the wait.

            :param duration: total time to sleep in seconds
            :param wid: id of wait thread
            :raises SignError: if LED sign unreachable

            Wait is cancelled when...
                CASE 1: display is changed to a different custom message before 
            the end of its wait time is reached and 'self.wait_id' will NOT 
            equal 'wid'.
                CASE 2: display is changed to drums or alert before the 
            end of its wait time is reached and the current display code will
            not be 1, 2 or 3. 

            *** Notify (display code 4) reverts to the previous display after
            10 seconds. If a custom message was playing before the notification, 
            once the notification is done it will set the display back to the custom 
            message even if the message wait time was reached while the notification 
            was playing. Therefore if the display code is 5 at the end of the 
            wait time we need to wait until it is no longer 5.
            """
            try:
                LOGGER.debug('wait time: ' + str(dur))
                r = int(dur / 20)
                for i in range(r):
                    LOGGER.debug(f'{dur -(i * 20)} secs remaining, id: {wid}')

                    for _ in range(4):  # 4 * 5 = 20
                        # check if wait cancelled
                        if (exit.is_set() or 
                            wid != self.wait_id or 
                            self.current_display not in [1, 2, 3, 5]):
                            LOGGER.info('wait canceled: ' + str(id))
                            return
                        exit.wait(5)

                # wait for notification to stop playing
                while self.current_display == NOTIFY_DISPLAY:
                    time.sleep(2)

                # Check wait was not canceled (CASE 1 and CASE 2)  
                if (wid == self.wait_id and 
                    self.current_display in [1, 2, 3]):  # info, danger, warning
                    try:
                        self._set_display('drums')  
                    except SignError:
                        LOGGER.warning('Sign Error in custom msg wait')
                    except SignLeaseError:
                        LOGGER.warning('Sign Lease Error in custom msg wait')
                
                else:   # custom message canceled, don't reset display 
                    LOGGER.info('wait canceled: ' + str(id))

            except Exception as exc:
                LOGGER.warning(f'Error in wait_thread - {exc}')

        #----------------------------------------------------------------------
        LOGGER.debug(f'dur {duration}, msg_type: {msg_type}, msg: {msg}')
        if self._has_priority(msg_type):
            display_code = int(msg_type)
            
            
            # wait for notification to stop
            while self.current_display == NOTIFY_DISPLAY:
                exit.wait(2)
            if exit.is_set():
                return
            
            LOGGER.info('Displaying custom message...')
            try:
                self._set_display(display_code, msg) 
                exit.wait(.5)  # allow time for other threads to run

                # start wait
                check_wait_id_reset()
                self.wait_id = self.wait_id + 1
                tr = threading.Thread(target=wait_thread, 
                                      args=(duration, self.wait_id))
                tr.start()
                self.intercom.announce_message(msg_type, msg)
                return True

            except SignError:
                LOGGER.info('Sign error in display_custom_msg()')
        return False

    def check_alarms(self, alarms):
        ''' Creates formated string of active alarm. If no active alarms 
        and alert is being displayed, changes display to drums. 
        
        :param alarms: dcs_data_pb2 Alarms message
        :return: True if check completed successfully, otherwise False
        :raises SignError: if LED sign is unreachable
        :raises InvalidParameter: if invalid alarm value received
        '''
        try:
            self.alarms['H2S'] = alarms.h2s
            self.alarms['LEL'] = alarms.lel
            self.alarms['FIRE'] = alarms.fire
            self.alarms['deck'] = alarms.deck
        except Exception as exc:
            self.alarms['H2S'] = False
            self.alarms['LEL'] =  False
            self.alarms['FIRE'] = False
            raise InvalidParameter(f'Invalid alarm flags recieved {exc}')

        alarms_str = ''
        if self.alarms['FIRE']:
            alarms_str = alarms_str + 'FIRE, '
        if self.alarms['H2S']:
            alarms_str = alarms_str + 'H2S, '
        if self.alarms['LEL']:
            alarms_str = alarms_str + 'LEL, '
        
        # alarm on
        if alarms_str != '':                       
            if len(alarms_str) > 6:    # length of one listed alarm
                alarms_str = alarms_str[:-7] +' & '+ alarms_str[-5:]
            alarms_str = alarms_str[:-2] + ' '
            self._turn_on_alert(alarms_str)

        # alarm off & alert playing
        elif self.current_display == ALERT_DISPLAY: 
            self._turn_off_alert()

        return True

    def display_notify(self, notify):
        """Displays notification for a short period of time, then reverts 
        display when done. Assumed that self.current_display at time fuction 
        is called is not 'alert'. Thus will never revert to an alert display.

        If prev_display is ERROR_DISPLAY then the DCS link is not 
        responding. If a notification is recevied then the DCS link has started 
        responding again and we don't want to revert back to the error message.
        Before the ERROR_DISPLAY was set the stages were unset so it is 
        safe to revert to DRUMS_DISPLAY.

        :param notify_code: dcs_data_pb2 Notification message
        :raises SignError: if LED sign is unreachable
        :raises SignLeaseError: if unable to acquire sign lease to set 
            display
        """
        prev_msg = self.current_msg
        prev_display = self.current_display

        try:
            self._set_display('notify', notify.sign_msg)
            time.sleep(.5)  # allow time for other threads to run
            self.intercom.announce_message('notify', notify.ts_msg)

            # revert after 'display_time' seconds
            time.sleep(notify.display_time)
            
            if prev_display in [DRUMS_DISPLAY, ERROR_DISPLAY]:   
                self._set_display(DRUMS_DISPLAY)
            else:
                self._set_display(prev_display, prev_msg)

        except SignLeaseError:
            LOGGER.warning('Sign Lease Error in display_notify()')
        except SignError:
            raise SignError()
        except Exception as exc:
            # since not SignLeaseError can assume lease was not returned
            self.sign.return_sign_lease()
            LOGGER.error(f'Error in display_notify - {exc}')
           
    def display_drums(self, override=False):
        try:
            if override:
                self._set_display('drums')
                return
            
            if self._has_priority('drums'):
                self._set_display('drums') 

        except SignLeaseError:
            LOGGER.warning('Sign Lease Error in display_drums()')
        except SignError:
            raise SignError()
        except Exception as exc:
            # since not SignLeaseError can assume lease was not returned
            self.sign.return_sign_lease()
            LOGGER.error(f'Error in display_drums - {exc}')

    def display_dcs_down(self):
        """Displays dcs down message on sign if no custom message is being 
        displayed.

        Does NOT allow _set_display() to throw SignError because there is 
        try block in dcs_update to handle it. Returns sign lease and leaves
        SignError to be thrown by different method.

        _has_priority() will return false if already playing 'error'
        """
        # 
        if self._has_priority('error'):   
            try:
                self._set_display('error', self.dcs_down_msg)  
                self._reset()

            except SignLeaseError:
                LOGGER.warning('Sign Lease error in display_dcs_down()')

            except Exception as exc:
                # since not SignLeaseError can assume lease was not returned
                self.sign.return_sign_lease()
                LOGGER.error(f'Error in display_notify - {exc}')

    def update_drum_states(self, drums):
        """Updates the current drum state by changing states displayed on 
        sign, saved values in self.drum_statess and the intercom box lights.

        Timers have priority over cycle stages. This means that the crum 
        cycle stage will only be displayed if there is no active timer.

        A sign lease is acquired for duration of for loop even though it is 
        only needed to call self.sign.update_drum_state().
        This is to ensure update is not interupted then unable to complete.

        :param stages: DrumStages message from dcs_data_pb2
        :raises SignError: if LED sign is unreachable
        """
        new_state = [ drums.D1A, drums.D1B, drums.D2A, 
                      drums.D2B, drums.D3A, drums.D3B ]
        try:    
            self.sign.get_sign_lease()       
            for drum, state in enumerate(new_state): 
                # if no active timer set stage
                if state.timer.type == NO_TIMER:
                    self.drum_states[drum]['timer'].CopyFrom(state.timer)
                    self._set_stage_state(state.stage, drum) 
                else:
                    self._set_timer_state(state.timer, drum)

            self.bootup = False
            self.sign.return_sign_lease()
        
        except SignLeaseError:
            LOGGER.warning('Sign lease error in update_drum_states')
        except SignError:
            raise SignError()       
        except Exception as exc:
            # since not SignLeaseError can assume lease was not returned
            self.sign.return_sign_lease()
            LOGGER.error(f'Error in display_notify - {exc}')

    def power_cycle(self):
        LOGGER.error('Sign is not responsding. Starting power cycle ...')
        try:
            self.intercom.power_cycle()
            exit.wait(60)  # sign boot up time

            if self.sign is not None:
                if self.current_display == ALERT_DISPLAY:
                    self.current_display = DRUMS_DISPLAY

                self.current_msg = self.sign.set_display(self.current_display, 
                    msg=self.current_msg)

            self.sign.return_sign_lease()   # reset after power cycle
            LOGGER.info('Power cycle successful.')

        except Exception as exc:
            LOGGER.error(f'Power cycle failed. {exc}')
            if not exit.is_set():
                self.power_cycle()  # try until successfull
