import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/vitamind/vitamin_d/vitamin_d_ws/install/vitamin_d'
