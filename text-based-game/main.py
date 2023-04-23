
from os import name
# import name module and name
from intro import *
from stats import *

# Call intro function
customName = intro(name)
print(str("Hello " + customName + "!"))

# Call the classType function
player = classSelect()
print( customName + ", you are a " + player + "!")

# Call the stats function
stats()
