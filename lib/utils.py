# CREATED: 27-APR-2023
# LAST EDIT: 28-APR-2023
# AUTHOR: DUANE RINEHART, MBA (drinehart@ucsd.edu)

'''ADMIN HELPER FUNCTIONS FOR DATA PROCESSING'''

import sys
def IsWin11():
    if sys.getwindowsversion().build > 22000:return True
    else:return False