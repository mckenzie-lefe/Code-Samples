from datetime import datetime as dt, timedelta
from helpers import int_to_bytes

class LEDSignCommand:
    """Holds all the codes needed for the LED sign commands as outlined in
    MCS Protocol v3.2

    Calls to functions set or append to self.cmd. When command is complete it
    can send 'self.cmd' to the LED sign.

    Partial command codes append to 'self.cmd'.

    METHODS THAT CREATE PARTIAL COMMANDS:
        start_cmd()                 end_cmd()                   write_to_txt()
        write_to_var()              append_cmd()                set_effect()
        set_position()              set_character_attribute()   set_font()
        set_color()                 set_pause()                 add_new_line()
        add_new_page()              add_tab_control()           add_countdown()
        add_date_time()             set_vspace()                set_hspace()
        set_speed()                 set_text_alignment()        set_text()
        embed_gif_file()            embed_var_file()            add_beep()

    METHODS THAT CREATE COMPLETE COMMANDS:
        create_var()                allocate_memory()           play_script()
        reset_sign()                clear_memory()              set_date()
        read_date()                 set_time()                  read_time()
        set_sign_address()          turn_off_sign()             turn_on_sign()
        get_free_memory()           list_files()                read_file()


    User can create a command by calling one of the complete command methods
    or by calling start_cmd() followed by one or more partial command methods,
    followed by end_cmd(). """

    def __init__(self, sign_addr):
        self.sign_addr = sign_addr
        self.cmd = None
        self.font = 4
        self.timer_font = 2
        self.stage_font = 1
        self.drum_font = 3
        self.drum_color = 'white'
        self.pause = 6        # secs between page flip for multi-line msgs

    #--- PARTIAL COMMAND METHODS -----------------------------------------------

    def start_cmd(self):
        self.cmd = '^B' + self.sign_addr+ '^A'

    def end_cmd(self):
        self.cmd = self.cmd + '^C'

    def append_cmd(self):
        self.cmd = '^A'

    def write_to_txt(self, filename):
        self.cmd = self.cmd + 'A$' + filename + '$'

    def write_to_var(self, filename):
        self.cmd = self.cmd + 'B$' + filename + '$'

    def set_effect(self, effect='H'):
        self.cmd = self.cmd + '^E'
        if 'explode' in effect:
            self.cmd = self.cmd + '$EXP$'
        elif 'pac' in effect:
            self.cmd = self.cmd + '$PAC$'
        elif 'scroll' in effect:
            self.cmd = self.cmd + '$SCU$'
        elif 'sleft' in effect:
            self.cmd = self.cmd + '$SCL$'
        elif 'flash' in effect:
            self.cmd = self.cmd + 'F'
        elif 'slide' in effect:
            self.cmd = self.cmd + 'C'
        else:
            self.cmd = self.cmd + 'H'

    def set_position(self, pos=None, x=0, y=0, w=256, h=32, a=4):
        self.cmd = self.cmd + '^P'
        if pos is not None:
            if 'mid' in pos:
                self.cmd = self.cmd + 'M'
            elif 'top' in pos:
                self.cmd = self.cmd + 'T'
            elif 'right' in pos:
                self.cmd = self.cmd + 'R'
            elif 'left' in pos:
                self.cmd = self.cmd + 'L'
            else:   #fill
                self.cmd = self.cmd + 'F'
        else:
            self.cmd = self.cmd + '$' + str(x) + ',' + str(y) + ',' + str(w) \
                + ',' + str(h) + ',' + str(a) + '$'

    def set_character_attribute(self, attribute):
        self.cmd = self.cmd + '^H'
        if 'flashOFF' in attribute:
            self.cmd = self.cmd + '0'
        elif 'flashON' in attribute:
            self.cmd = self.cmd + '1'

        if 'wideOFF' in attribute:
            self.cmd = self.cmd + '2'
        elif 'wideON' in attribute:
            self.cmd = self.cmd + '3'

        if 'boldOFF' in attribute:
            self.cmd = self.cmd + '4'
        elif 'boldON' in attribute:
            self.cmd = self.cmd + '5'

    def set_font(self, font):
        self.cmd = self.cmd + '^F'
        if font == 0:
            self.cmd = self.cmd + '$AR12$'
        elif font == 1:
            self.cmd = self.cmd + '$AR16$'
        elif font == 2:
            self.cmd = self.cmd + '$AR24$'
        elif font == 3:
            self.cmd = self.cmd + '$ARN9$'
        # old timer font -> only has [1 - 9, :]
        elif font == 4:
            self.cmd = self.cmd + '$SS4$'
        elif font == 5:
            self.cmd = self.cmd + '$SS5$'
        # old timer font
        elif font == 6:
            self.cmd = self.cmd + '$SS7$'
        # iso timer font
        elif font == 7:
            self.cmd = self.cmd + '$SS8$'
        elif font == 8:
            self.cmd = self.cmd + '$SS15$'
        elif font == 9:
            self.cmd = self.cmd + '$SS16$'
        elif font == 10:
            self.cmd = self.cmd + '$SS24$'
        elif font == 11:
            self.cmd = self.cmd + '$SF7$'
        elif font == 12:
            self.cmd = self.cmd + '$SF8$'
        elif font == 13:
            self.cmd = self.cmd + '$SF10$'
        elif font == 14:
            self.cmd = self.cmd + '$SF15$'
        elif font == 15:
            self.cmd = self.cmd + '$SF16$'
        elif font == 16:
            self.cmd = self.cmd + '$SF24$'
        elif font == 17:
            self.cmd = self.cmd + '$SMA$'
        elif font == 18:
            self.cmd = self.cmd + '$FX7$'
        elif font == 19:
            self.cmd = self.cmd + '$FX15$'
        # Drum Label -> only Has [1, 2, 3, A, B]
        elif font == 20:
            self.cmd = self.cmd + '$FXC$'
        elif font == 21:
            self.cmd = self.cmd + '$TM12$'
        elif font == 22:
            self.cmd = self.cmd + '$TM16$'
        elif font == 23:
            self.cmd = self.cmd + '$TM24$'
        # Alert msg font
        elif font == 24:
            self.cmd = self.cmd + '$TT$'
        # Timer font
        elif font == 25:
            self.cmd = self.cmd + '$ISO7$'
        # Stage font
        elif font == 26:
            self.cmd = self.cmd + '$CS15$'
        # Custom msg Label font
        elif font == 27:
            self.cmd = self.cmd + '$IM15$'
        else:
            self.cmd = self.cmd + '$' + str(font) + '$'

    def set_color(self, color):
        self.cmd = self.cmd + '^O'
        if 'red' in color:
            self.cmd = self.cmd + '0'
        elif 'green' in color:
            self.cmd = self.cmd + '1'
        elif 'yellow' in color:
            self.cmd = self.cmd + '2'
        elif 'rain' in color:
            self.cmd = self.cmd + '3'
        elif 'blue' in color:
            self.cmd = self.cmd + '$BLU$'
        elif 'purple' in color:
            self.cmd = self.cmd + '$PUR$'
        elif 'white' in color:
            self.cmd = self.cmd + '$WHT$'
        elif 'pink' in color:
            self.cmd = self.cmd + '$F:rgb(159,43,104)$'
        else:
            self.cmd = self.cmd + '$F:rgb' + str(color) + '$'

    def set_pause(self, s):
        s_hex = int_to_bytes(s, 1).hex()
        self.cmd = self.cmd + '^J' + s_hex

    def add_new_line(self):
        self.cmd = self.cmd + '^M'

    def add_new_page(self):
        self.cmd = self.cmd + '^L'

    def add_tab_control(self, a, pos=None):
        """ Optional param 'pos' is 1-4 decimal chars which is the absolute
        coord in horizontal """
        self.cmd = self.cmd + '^T'
        if pos is not None:
            self.cmd = self.cmd + '$'

        if 'left' in a:
            self.cmd = self.cmd + '0'
        elif 'right' in a:
            self.cmd = self.cmd + '1'
        elif 'center' in a:
            self.cmd = self.cmd + '2'
        elif 'decimal point':
            self.cmd = self.cmd + '3'

        if pos is not None:
            self.cmd = self.cmd + ',' + str(pos) + '$'

    def add_countdown(self, dt_str=None, mins=0, secs=0):
        if dt_str is None:
            now = dt.now()
        else:
            now = dt(int(dt_str[4:8]), int(dt_str[:2]), int(dt_str[2:4]), 
                     int(dt_str[9:11]), int(dt_str[11:13]), int(dt_str[13:15]))
            #print(now)

        delay = now + timedelta(minutes=mins, seconds=secs)
        countdown = delay.strftime("%m-%d-%Y %H:%M:%S")
        self.cmd = self.cmd + '^R$16, ' + countdown + '$'

    def add_date_time(self, element):
        """ ^K followed by two ASCII characters
            First ASCII character:
                0   do not show leading zeros
                1   show leading zeros
                2   show leading seros as spaces
                5   show as all caps
                6   show as lowercase
                7   show as first-letter caps

            Second ASCII character:
                0   numeric day
                1   numeric month
                2   numeric year last 2 digits only
                3   numeric year all four digits
                4   month abbreviation
                5   month full name
                6   day of the week abbreviation
                7   day of the week full name
                8   hour in 12-hour mode
                9   hour in 24-hour mode
                A   minute
                B   second
                C   AM/PM as a single character A/P
                D   AM/PM as two characters AM/PM
                E   suffix of the dat like 'st','nd', 'rd', ot 'th'
        """
        if element in ['time24', 'time']:
            self.cmd = self.cmd + '^K19'
        elif element in ['time12']:
            self.cmd = self.cmd + '^K18'
        elif element in ['num_date', 'date']:
            # needs to be tested, not sure if text ('/') will work in between ^K
            self.cmd = self.cmd + '^K10/^K11/^K12'
        elif element in ['full_txt_date', 'txt_data']:
            # needs to be tested, not sure if text will work in between ^K
            self.cmd = self.cmd + '^K77, ^K75 ^K00^K6E, ^k03'

    def set_vspace(self, space):
        """ 'space' param is one character '0' to '9' """
        self.cmd = self.cmd + '^U$3,' + str(space) + '$'

    def set_hspace(self, space):
        """ 'space' param is one character '0' to '9' """
        self.cmd = self.cmd + '^U$2,' + str(space) + '$'

    def set_speed(self, speed):
        """ 'speed' must be a characters between '1' and '8', where 1 is slow
        and 8 is fast. NOTE: default speed is 3"""
        assert type(speed) == str
        self.cmd = self.cmd + '^I' + speed

    def set_text_alignment(self, a):
        self.cmd = self.cmd + '^U'
        if 'lt' in a:       # left, top
            self.cmd = self.cmd + '0'
        elif 'ct' in a:     # center, top
            self.cmd = self.cmd + '1'
        elif 'rt' in a:     # right, top
            self.cmd = self.cmd + '2'
        elif 'lm' in a:     # left, middle
            self.cmd = self.cmd + '3'
        elif 'rm' in a:     # right, middle
            self.cmd = self.cmd + '5'
        elif 'lb' in a:     # left, bottom
            self.cmd = self.cmd + '6'
        elif 'cb' in a:     # center, bottom
            self.cmd = self.cmd + '7'
        elif 'rb' in a:     # right, bottom
            self.cmd = self.cmd + '8'
        else:               # center, middle
            self.cmd = self.cmd + '4'

    def set_text(self, txt):
        self.cmd = self.cmd + txt

    def embed_gif_file(self, filename):
        fn = filename.split('.')[0] + '.gif'
        self.cmd = self.cmd + '^S$' + fn + '$'

    def embed_bmp_file(self, filename):
        fn = filename.split('.')[0] + '.bmp'
        self.cmd = self.cmd + '^S$' + fn + '$'

    def embed_var_file(self, filename):
        self.cmd = self.cmd + '^N$' + filename + '$'

    def add_beep(self, b):
        """ b is character between '1' and '4' """
        self.cmd = self.cmd + '^V' + str(b)

    #-- COMPLETE COMMAND METHODS -----------------------------------------------

    def create_var_file(self, size, filename):
        """filename should not include .EXT"""
        hex_size = int_to_bytes(size, 2).hex()
        self.start_cmd()
        self.cmd = self.cmd + 'CSM$' + filename + '$V' + hex_size
        self.end_cmd()

    def allocate_memory(self, size, filename):
        """ Needed to create new test files on sign.
        Helper for send_file(), as memory allocation must be made before sending
        file to sign."""
        self.start_cmd()
        hex_size = int_to_bytes(size, 4).hex()
        self.cmd = self.cmd + 'CFM' + filename + '=' + hex_size
        self.end_cmd()

    def play_script(self, filename, reset=True):
        if filename[-3:] != '.sh':
            filename = filename + '.sh'

        self.start_cmd()
        #self.cmd = self.cmd + 'E$cmd$play {' + filename + '}
        #from {21/11/2021 14:52} to {21/11/2022 15:0}^C'
        self.cmd = self.cmd + 'E$cmd$play {' + filename + '}^C'

    def reset_sign(self):
        self.start_cmd()
        self.cmd = self.cmd + 'CQR'
        self.end_cmd()

    def clear_memory(self):
        self.start_cmd()
        self.cmd = self.cmd + 'CCM'
        self.end_cmd()

    def set_date(self, mm, dd, yyyy, x):
        """ mm = month, '01' to '12'
            dd = day, '01' to '31'
            yyyy = year, '2000' to '2099'
            x = day of week, 0=Sunday to 6=Saturday
        """
        self.start_cmd()
        self.cmd = self.cmd + 'CSD' + mm + dd + yyyy + x
        self.end_cmd()

    def set_time(self, hh, mm, ss):
        """ hh = hour, '00' to '23'
            mm = minute, '00' to '59'
            ss = second, '00' to '59'
        """
        self.start_cmd()
        self.cmd = self.cmd + 'CST' + hh + mm + ss
        self.end_cmd()

    def read_date(self):
        self.start_cmd()
        self.cmd = self.cmd + 'CRD'
        self.end_cmd()

    def read_time(self):
        self.start_cmd()
        self.cmd = self.cmd + 'CRT'
        self.end_cmd()

    def set_brightness(self, b):
        self.start_cmd()
        self.cmd = self.cmd + 'CWFbrightmode=0\r\nbrightness=' + b + '\r\n^C'

    def set_sign_address(self, addr):
        """ addr param must be a hex string between '0' and 'FF' """
        self.start_cmd()
        self.cmd = self.cmd + 'CSA' + addr
        self.end_cmd()

    def turn_off_sign(self):
        self.start_cmd()
        self.cmd = self.cmd + 'CPF'
        self.end_cmd()

    def turn_on_sign(self):
        self.start_cmd()
        self.cmd = self.cmd + 'CPO'
        self.end_cmd()

    def get_free_memory(self):
        self.start_cmd()
        self.cmd = self.cmd + 'CRM'
        self.end_cmd()

    def list_files(self):
        self.start_cmd()
        self.cmd = self.cmd + 'CFL*.*'
        self.end_cmd()

    def read_file(self, filename):
        self.start_cmd()
        self.cmd = self.cmd + 'CFR' + filename
        self.end_cmd()
