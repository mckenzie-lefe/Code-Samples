import threading
from datetime import timedelta, datetime as dt
from XXXX import PITags
from XXXX import *


class NotificationHandler(PITags): 
    def __init__(self, log):
        PITags.__init__(self)
        self.log = log 

        self.PC_watcher = False
        self.PC_check = 1

        self.BC_watcher = False
        self.drain_valve_states = [ 
            'Closed', 'Closed', 'Closed', 
            'Closed', 'Closed', 'Closed'
        ]

        self.last_BWs = [
            dt(2022, 1, 1, 1, 1, 1, 0), dt(2022, 1, 1, 1, 1, 1, 0), dt(2022, 1, 1, 1, 1, 1, 0),
            dt(2022, 1, 1, 1, 1, 1, 0), dt(2022, 1, 1, 1, 1, 1, 0), dt(2022, 1, 1, 1, 1, 1, 0)
        ]

        self.activation_time = dt.now()
        self.active_notification = False 
        self.notify = { 
            'code': 'NNN', 
            'type': 'none', 
            'event': 'none', 
            'drum': 'none'
        }

        self.lock = threading.Lock()

    def _drum_pos_to_name(self, pos):
        if pos == 0:
            return '1A'
        elif pos == 1:
            return '1B'
        elif pos == 2:
            return '2A'
        elif pos == 3:
            return '2B'
        elif pos == 4:
            return '3A'
        elif pos == 5:
            return '3B'
        else:
            print('Invalid drum position')
            return 'N'

    def _get_mins_till(self):
        time_till = dt.now() - self.activation_time 
        secs_till = time_till.seconds % 60
        mins_till = round((time_till.seconds - secs_till) / 60) 

        return mins_till

    def _get_warning_ts_txt(self):
        mins_till = self._get_mins_till()

        if self.notify['event'] == 'pilot':
            ts_msg = "Attention all personnel working on the coker " +\
                "structure, the pilot on " +self.notify['drum']+ \
                " will begin in " +str(mins_till)+ " minutes. Please vacate" + \
                " the structure or get to a safe area." 
        else:
            if self.notify['drum'] == '1A':
                train = 'Train 1'
            elif self.notify['drum']== '1B':
                train ='Train 1 and 2A'
            elif self.notify['drum'] == '2A':
                train = 'Train 2 and 1B'
            elif self.notify['drum'] == '2B':
                train ='Train 2 and 3A'
            elif self.notify['drum'] == '3A':
                train = 'Train 3 and 2B'
            elif self.notify['drum'] == '3B':
                train ='Train 3 and 2A'
            else:
                return ""

            if self.notify['event'] == 'blowdown':
                event_ts = 'blowing down'
            else:
                event_ts = self.notify['event']

            if mins_till <= 1:
                mins = str(mins_till) + ' minute.'
            else:
                mins = str(mins_till) + ' minutes.'

            ts_msg = "Attention all personnel working on the coker " + \
                "structure, above or below the switch deck. We will be " + \
                event_ts+ " " +self.notify['drum']+ " in approximately " \
                +mins+ " If you are in the vicinity of " \
                +train.replace("and", "or")+ ", above or below the switch " + \
                "deck, please vacate the area."
        
        return ts_msg
    
    def _get_warning_sign_txt(self):
        mins_till = self._get_mins_till()

        if self.notify['event'] == 'pilot':
            train = "Coker Structure"
        else:
            if self.notify['drum'] == '1A':
                train = 'Train 1'
            elif self.notify['drum']== '1B':
                train ='Train 1 and 2A'
            elif self.notify['drum'] == '2A':
                train = 'Train 2 and 1B'
            elif self.notify['drum'] == '2B':
                train ='Train 2 and 3A'
            elif self.notify['drum'] == '3A':
                train = 'Train 3 and 2B'
            elif self.notify['drum'] == '3B':
                train ='Train 3 and 2A'
            else:
                return ""

        if mins_till <= 1:
            mins = str(mins_till) + ' min.'
        else:
            mins = str(mins_till) + ' mins.'

        sign_msg = "Attention: " +self.notify['drum']+ " " \
            +self.notify['event']+ " begins in " +mins+ " Vacate " +train 
        
        return sign_msg
    
    def _get_complete_ts_txt(self):
        ts_msg = "Attention all personnel working on the coker structure, " + \
            "the "+self.notify['event']+ " on " +self.notify['drum']+ \
            " is now complete." 

        if self.notify['event'] == 'pilot':
            if self.notify['drum'] == '1A':
                train = 'Train 1 and 3'
            elif self.notify['drum'] == '1B':
                train ='Train 3 and 2B'
            elif self.notify['drum'] == '2A':
                train = 'Train 1 and 1A'
            elif self.notify['drum'] == '2B':
                train ='Train 1 and 3B'
            elif self.notify['drum'] == '3A':
                train = 'Train 1 and 2A'
            elif self.notify['drum'] == '2B':
                train ='Train 1 and 2'

            return ts_msg + " All workers on " +train+ \
                " can return to work."
        
        if self.notify['event'] == 'cut':
            return ts_msg + \
                " All workers can access all trains until further notice."

        return ts_msg

    def _get_complete_sign_txt(self):
        return "Attention: " +self.notify['drum']+ " " \
            +self.notify['event']+ " complete. "  

    def _blowdown_warning(self, pos):
        drum_pressure = int(self.get_tag_value(self.drum_tags[pos]['BW']))
        if drum_pressure > 200 and (dt.now() - self.last_BWs[pos]) > timedelta(minutes=180):
            return True

        return False

    def _is_pilot_complete(self, pos):
        stem_pos = int(self.get_tag_value(self.drum_tags[pos]['PC']))

        if ((self.PC_check in [1, 3] and stem_pos < 5) or 
            (self.PC_check in [2, 4] and stem_pos > 33)):
            self.PC_check += 1
            
        if self.PC_check >= 5:
            self.PC_check = 1       # reset 
            return True

        return False
    
    def _is_blowdown_complete(self, pos):
        is_complete = False
        state = str(self.get_tag_value(self.drum_tags[pos]['BC']))
        
        if (self.drain_valve_states[pos] == 'Undefined' and 
            state == 'Closed'):
            is_complete = True

        self.drain_valve_states[pos] = state
        return is_complete

    def _turn_off_notification(self):
        """Checks if current active notification can be turned off.
        Complete notifications can are to be turned off after 3 minutes.
        Warning notifications can be turned off after 10 minutes.
        """
        if  (self.active_notification and 
            ((self.notify['type'] == 'complete' and 
              dt.now() - self.activation_time > timedelta(minutes=3)) or 
             (self.notify['type'] == 'warning' and 
              dt.now() - self.activation_time > timedelta(minutes=10)))):
            
            self.active_notification = False 
            self.log.put('notify OFF')

    def _get_sign_txt(self):
        if self.notify['type'] == 'warning':
            return self._get_warning_sign_txt()
        
        if self.notify['type'] == 'complete':
            return self._get_complete_sign_txt()
        
        return ""

    def _get_ts_txt(self):
        if self.notify['type'] == 'warning':
            return self._get_warning_ts_txt()
        
        if self.notify['type'] == 'complete':
            return self._get_complete_ts_txt()
        
        return ""

    def _get_display_time(self):
        if self.notify['type'] == 'warning':
            return WARNING_DISPLAY_TIME
        
        if self.notify['type'] == 'complete':
            return COMPLETE_DISPLAY_TIME
        
        return 0.0

    def check_notifications(self, old_stage, new_stage, drum_pos):
                    #### ADD NOTIFY condition check here. ####
        #### Note: Consider priorty of notify when inserting to if-else ####  
        try:
            if old_stage == 'Press Test' and new_stage == 'Transition':
                self.BC_watcher = True # turn on watcher

            # Draining Warining
            if new_stage == 'Venting':
                with self.lock:
                    self.activation_time = dt.now()    
                    self.active_notification = True
                    self.notify['code'] = 'WD' + str(drum_pos)
                    self.notify['type'] = 'warning'
                    self.notify['event'] = 'draining'
                    self.notify['drum'] = self._drum_pos_to_name(drum_pos)

            # Pilot Warning 
            elif (old_stage in ['Draining', 'Transition'] and 
                new_stage == 'Cutting'):
                with self.lock:
                    self.activation_time = dt.now()    
                    self.active_notification = True
                    self.notify['code'] = 'WP' + str(drum_pos)
                    self.notify['type'] = 'warning'
                    self.notify['event'] = 'pilot'
                    self.notify['drum'] = self._drum_pos_to_name(drum_pos)
                    self.PC_watcher = True      # turn on watcher

            # Pilot Complete 
            elif self.PC_watcher and self._is_pilot_complete(drum_pos):
                with self.lock:
                    self.activation_time = dt.now()    
                    self.active_notification = True
                    self.notify['code'] = 'CP' + str(drum_pos)
                    self.notify['type'] = 'complete'
                    self.notify['event'] = 'pilot'
                    self.notify['drum'] = self._drum_pos_to_name(drum_pos)
                    self.PC_watcher = False     # turn off watcher

            # Cutting Complete
            elif old_stage == 'Cutting' and new_stage == 'Transition':
                with self.lock:
                    self.activation_time = dt.now()    
                    self.active_notification = True
                    self.notify['code'] = 'CC' + str(drum_pos)
                    self.notify['type'] = 'complete'
                    self.notify['event'] = 'cut'
                    self.notify['drum'] = self._drum_pos_to_name(drum_pos)

            # Blowdown Warning
            elif (new_stage == 'Press Test' and 
                  self._blowdown_warning(drum_pos)):
                with self.lock:
                    self.last_BWs[drum_pos] = dt.now()
                    self.activation_time = dt.now()    
                    self.active_notification = True
                    self.notify['code'] = 'WB' + str(drum_pos)
                    self.notify['type'] = 'warning'
                    self.notify['event'] = 'blowdown'
                    self.notify['drum'] = self._drum_pos_to_name(drum_pos)

            # Blowdown Complete
            elif self.BC_watcher and self._is_blowdown_complete(drum_pos):
                with self.lock:
                    self.activation_time = dt.now()    
                    self.active_notification = True
                    self.notify['code'] = 'CB' + str(drum_pos)
                    self.notify['type'] = 'complete'
                    self.notify['event'] = 'blowdown'
                    self.notify['drum'] = self._drum_pos_to_name(drum_pos)
                    self.BC_watcher = False  # turn off watcher

            self._turn_off_notification()

        except Exception as exc:
            self.log.put(f'Error in check_notifications - {exc}')

    def get_notify_msg(self, notify):
        """Creates Notification message holding details of current notification

        :param client: dictionary containing data about last notification 
            client received
        :param notify: Response message notify field value
        """
        if self.active_notification:
            notify.sign_msg = self._get_sign_txt() 
            notify.ts_msg = self._get_ts_txt()
            notify.display_time = self._get_display_time()
            notify.code = self.notify['code']
        else:
            notify.code = 'NNN'
            