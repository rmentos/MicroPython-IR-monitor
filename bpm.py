from machine import I2C, Pin
import time
import array

# MAX30101 I2C address
MAX30101_I2C_ADDRESS = 0x57

# MAX30101 registers
REG_FIFO_DATA = 0x07
REG_FIFO_WR_PTR = 0x04
REG_FIFO_RD_PTR = 0x06
REG_INTR_STATUS_1 = 0x00
REG_INTR_STATUS_2 = 0x01

# Initialize I2C with a lower frequency for better stability
i2c = I2C(1, scl=Pin(27), sda=Pin(26), freq=1000) 

def max30101_write_register(register, value):
    try:
        i2c.writeto_mem(MAX30101_I2C_ADDRESS, register, bytes([value]))
        print(f"Successfully wrote {value} to register {register} at address {hex(MAX30101_I2C_ADDRESS)}")
    except OSError as e:
        print(f"Error writing to register {register}: {e}")

def max30101_read_register(register):
    try:
        value = i2c.readfrom_mem(MAX30101_I2C_ADDRESS, register, 1)[0]
        print(f"Read {value} from register {register} at address {hex(MAX30101_I2C_ADDRESS)}")
        return value
    except OSError as e:
        print(f"Error reading from register {register}: {e}")
        return 0


def max30101_init():
    # Reset the sensor
    max30101_write_register(0x09, 0x40)
    time.sleep(1)
    
    # Clear the FIFO write pointer, read pointer, and overflow counter
    max30101_write_register(0x04, 0x00)
    max30101_write_register(0x06, 0x00)
    max30101_write_register(0x05, 0x00)

    # Interrupt configuration (disable all interrupts)
    max30101_write_register(0x02, 0x00)
    max30101_write_register(0x03, 0x00)
    
    # FIFO configuration (sample averaging = 4, FIFO rollover = enabled, FIFO almost full = 17)
    max30101_write_register(0x08, 0x4F)
    
    # Mode configuration (SpO2 mode)
    max30101_write_register(0x09, 0x03)
    
    # SpO2 configuration (ADC range = 4096 nA, sample rate = 100 Hz, pulse width = 411 us)
    max30101_write_register(0x0A, 0x27)
    
    # LED pulse amplitudes
    max30101_write_register(0x0C, 0x24) # Red LED
    max30101_write_register(0x0D, 0x24) # IR LED
    
def read_fifo():
    try:
        data = i2c.readfrom_mem(MAX30101_I2C_ADDRESS, REG_FIFO_DATA, 6)
        red = (data[0] << 16 | data[1] << 8 | data[2]) & 0x03FFFF
        ir = (data[3] << 16 | data[4] << 8 | data[5]) & 0x03FFFF
        return red, ir
    except OSError as e:
        print(f"Error reading FIFO data: {e}")
        return 0, 0

def my_sum(data_input):
    result = 0
    for e in data_input:
        result += e
    return result

def moving_average (ir_data,interval):
  averaged=[]

  for start in range(0,len(ir_data)-interval):
    averaged.append(my_sum(ir_data[start:start+interval])/interval)

  return averaged

def remove_back(ir_data, average):
    background_removed=[]

    for x in range(0,236):
      background_removed.append(ir_data[x]-average[x])

    return background_removed

def normalize_list(input_list):
    listmax = max(input_list)
    normalize = [x/listmax for x in input_list]
    return normalize
#     normalized = normalize_list(background_removed)

def ac(normalized_data):
    max_shift=100
    ac=[]

    for shift in range(0,max_shift):
      total=0
      for x in range(0,100):
        total=total+normalized_data[x]*normalized_data[x+shift]
      ac.append(total)
    ac_len=len(ac)
    
def detect_heartbeat(ir_values, threshold=50000):
    peaks = []
    for i in range(1, len(ir_values) - 1):
        if ir_values[i] > ir_values[i - 1] and ir_values[i] > ir_values[i + 1] and ir_values[i] > threshold:
            peaks.append(i)
    return peaks

def remove_background(data, averaged):
    background_removed=[]
    for x in range(0,482):
        background_removed.append(data[x]-averaged[x])
    return background_removed

def normalize_list(input_list):
  listmax = max(input_list)
  normalize = [x/listmax for x in input_list]
  return normalize

def ac(input_data):
    max_shift=100
    ac=[]

    for shift in range(0,max_shift):
        total=0
        for x in range(0,300):
            total=total+input_data[x]*input_data[x+shift]
        ac.append(total)

    
    return ac

def find_maxima(inputList):
    result = [0] * len(inputList)

    a = inputList[0]
    b = inputList[1]
    distance_between =0
    goingUp = a <= b

    for i in range(1, len(inputList) - 2):
        a = inputList[i]
        b = inputList[i + 1]
        

        if goingUp:
            if a > b :
                result[i] = a
                goingUp = False
                
        else:
            if b > a:
                goingUp = True
                

    return result
def time_between(maximas):
    time_maxes = []
    found_num = False
    count = 0
    for element in maximas:
        if element > 0 and not found_num:
            found_num = True
        elif element > 0 and  found_num:
            time_maxes.append(count)
            count = 0
        elif found_num:
            count = count + 1
        else:
            continue
    return time_maxes

def per_minute(intervals_length, time_miliseconds, interval_time): #interval length: time between maximas, time_miliseconds: elapsed time to get dataset
    tick_time = time_miliseconds/interval_time 
    average_interval = sum(intervals_length) / len(intervals_length)
    average_distance = 1 / average_interval
    convert_to_seconds = (average_distance * (interval_time/time_miliseconds)) * 1000
    convert_to_minutes = convert_to_seconds *60
    rounded = round(convert_to_minutes)
    return rounded
    

# Perform I2C scan
devices = i2c.scan()
if not devices:
    print("No I2C devices found")
else:
    print(f"I2C devices found: {devices}")
    
    
# Initialize the MAX30101 sensor
max30101_init()

# Buffer to store IR values
buffer_size = 100
ir_values = array.array('I', [0] * buffer_size)
index = 0

start_time = time.ticks_ms()

counter = 0
i = 0
interval_l = 512
ir_data = []
#test_data = [27420, 27412, 27459, 27503, 27520, 27564, 27602, 27629, 27677, 27706, 27713, 27714, 27698, 27689, 27700, 27646, 27539, 27470, 27421, 27408, 27447, 27495, 27528, 27571, 27610, 27644, 27667, 27703, 27732, 27758, 27772, 27780, 27800, 27796, 27695, 27579, 27497, 27460, 27447, 27466, 27513, 27552, 27580, 27602, 27628, 27662, 27694, 27730, 27774, 27808, 27831, 27845, 27857, 27813, 27687, 27601, 27537, 27498, 27500, 27547, 27602, 27634, 27664, 27678, 27698, 27707, 27703, 27700, 27719, 27763, 27817, 27860, 27887, 27875, 27753, 27661, 27609, 27571, 27569, 27615, 27661, 27700, 27730, 27757, 27790, 27824, 27850, 27862, 27860, 27857, 27867, 27878, 27872, 27798, 27672, 27576, 27502, 27457, 27458, 27479, 27485, 27485, 27495, 27502, 27511, 27547, 27579, 27606, 27615, 27627, 27644, 27661, 27665, 27594, 27491, 27385, 27292, 27245, 27254, 27299, 27338, 27361, 27383, 27409, 27446, 27488, 27516, 27544, 27572, 27598, 27615, 27641, 27669, 27676, 27573, 27452, 27366, 27314, 27289, 27318, 27362, 27399, 27414, 27443, 27466, 27496, 27529, 27547, 27556, 27553, 27573, 27601, 27634, 27674, 27687, 27612, 27565, 27533, 27523, 27542, 27587, 27628, 27628, 27632, 27653, 27689, 27703, 27692, 27704, 27739, 27785, 27823, 27850, 27867, 27871, 27785, 27734, 27692, 27647, 27634, 27667, 27693, 27637, 27596, 27631, 27694, 27749, 27766, 27765, 27764, 27776, 27796, 27832, 27868, 27838, 27717, 27641, 27596, 27577, 27569, 27597, 27634, 27644, 27675, 27720, 27737, 27735, 27746, 27765, 27785, 27819, 27847, 27840, 27800, 27687, 27611, 27556, 27539, 27532, 27548, 27612, 27664, 27695, 27694, 27692, 27724, 27759, 27790, 27828, 27845, 27860, 27851, 27817, 27734, 27663, 27564, 27491, 27503, 27551, 27580, 27599, 27628, 27641, 27655, 27692, 27708, 27725, 27762, 27799, 27834, 27844, 27777, 27663, 27572, 27517, 27512]
while True:
    red, ir = read_fifo()
    ir_values[index] = ir
    index = (index + 1) % buffer_size
    ir_data.append(ir)

    i = i + 1
    if i == interval_l:
        end_time = time.ticks_ms()
        elapsed_time = time.ticks_diff(end_time, start_time)
        #print(elapsed_time)
        start_time = time.ticks_ms()
        average = moving_average(ir_data,30)
        cleaned_up = remove_background(ir_data,average)
        normalized = normalize_list(cleaned_up)
        ac_data = ac(normalized)
        fm = find_maxima(ac_data)
        time_list = time_between(fm)
        BPM = per_minute(time_list, elapsed_time, interval_l)
        print("BPM: " + str(BPM) + " beats per minute")
        ir_data = []
        i = 0
        

    