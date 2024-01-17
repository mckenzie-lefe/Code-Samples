import threading
from XXXX import *
from XXXX import PITags


class AlarmHandler(PITags): 
    def __init__(self, log):
        PITags.__init__(self)
        self.log = log

        self.states = []
        for _, _ in enumerate(self.alarms):
            self.states.append(OFF)

        self.lock = threading.Lock()

    def _is_alarm_on(self, alarm):
        val = str(self.get_tag_value(alarm['tag']))
        try:
            if val == 'Bad Input':
                 return False 
            
            if alarm["type"] == 'FIRE' and val not in ['0', '1'] :
                self.log.put(f'Unrecongized fire value from PI. val: {val}')
                return False

            # check fire alarm and LEL & H2S alarms on switch deck         
            if ((alarm["type"] == FIRE and val == '1') or  
                (alarm["type"] in [H2S, LEL] and 
                    alarm["deck"] == SWITCH_DECK and 
                    float(val) > ALARM_THRES_LOW)):  
                # LEL & H2S alarms  on cut deck -- DISABLED
                ## or (alarm["deck"] == CUT_DECK and float(val) > ALARM_THRES_HIGH)  

                self.log.put(f'{alarm["type"]} ON -- val: {val}') 
                return True 
            
        except Exception as exc:
            self.log.put(f'Error checking alarm val: {val}\n{exc}')
        return False

    def _start_alarm_delay(self, state_id, alarm):
        '''Waits 'ALARM_DELAY' seconds then checks the PI alarm tag value. 
            If PI value indicates alarm is on then sets alarm state to ON. 
            this will trigger the annunciator to play an alert. 

            Assumes that alarm['state'] = DELAY 
            :param alarm: dictionary holding the information of one alarm
        '''
        def delay_thread():
            if DEBUG:
                r = int(ALARM_DELAY / 20)
                for i in range(r):
                    s = ALARM_DELAY -(i * 20)
                    self.log.put(f'{s} secs till {alarm["type"]} alarms')
                    exit.wait(20)
            else:
                exit.wait(ALARM_DELAY)

            if not exit.is_set():
                if self._is_alarm_on(alarm): 
                    with self.lock:
                        self.states[state_id] = ON     # trigger announcement
                    return

                self.log.put(f'False alarm - {alarm["tag"]}')
                self.states[state_id] = OFF
        # ---------------------------------------------------------------------
        
        self.log.put(f'Starting alarm delay for {alarm["tag"]}...')
        tr = threading.Thread(target=delay_thread)
        tr.start()

    def check_alarms(self):
        '''Retrieves & processes gas and fire data from PI.

        If the data from PI indicates an alarm is ON, starts the alarm delay 
        timer thread which waits 'ALARM_DELAY' seconds before checking the PI
        alarm value again. This is to prevent false alarms from playing. 
        Otherwise, it will set alarm state to OFF. 

        If an alarm state has been set as ON it will trigger the annunciator 
        to play the alert. In order for the alert to be turned off all alarms 
        which have the same type need to be in the OFF state.
        '''
        for idx, alarm in enumerate(self.alarms):
            if self._is_alarm_on(alarm): 
                # alarm is not on & delay hasn't started yet
                if self.states[idx] == OFF:   
                    self._start_alarm_delay(alarm)
                    self.states[idx] = DELAY
                continue    # skip turnning off alarm
           
            self.states[idx] = OFF
        # END FOR -------------------------------------------------------------   

    def get_alarms_msg(self, msg):
        """Checks status code of the alarms and alarm message fields 
        accordingly.

        An alarm flag is turned on when any of the alarms that corresponde to 
        it (alarms with alarm[0][1] = H2S/LEL/FIRE) indicate that they are on 
        (alarm[1] = 1). 

        An alarm will be turned of when all of the alarms that corresponde to 
        it (alarms with alarm[0][1] = H2S/LEL/FIRE) indicate that they are off 
        (alarm[1] = 0).

        :param alarms_msg: 
        """    
        msg.lel = False
        msg.fire = False
        msg.h2s = False
        msg.deck = NO_DECK
        msg.active_alarm = False

        for idx, alarm in enumerate(self.alarms):
            with self.lock:
                if self.states[idx] == ON:
                    msg.active_alarm = True

                    if msg.deck == NO_DECK:
                        msg.deck = alarm['deck']
                    elif msg.deck != alarm['deck']:
                        msg.deck = BOTH_DECKS

                    if alarm["type"] == H2S:
                        msg.h2s = True
                    elif alarm["type"] == LEL:
                        msg.lel = True
                    elif alarm["type"] == FIRE:
                        msg.fire = True
            exit.wait(0.1)      # allow time for other threads