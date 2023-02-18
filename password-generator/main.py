import random
import string

# Prompt user for password length (must be INT)
length = int(input("How many characters would you like your password to be? "))

# Make sure password length is at least 8 characters but less than 64
while length < 8 or length > 64:
    print("Password must be at least 8 characters but less than 64.")
    length = int(input("How many characters would you like your password to be? "))

# Create a list of characters to choose from
chars = string.ascii_letters + string.digits + string.punctuation

# Create a password
password = ""
for i in range(length):
    password += random.choice(chars)
    
# Print the password
print(password)




