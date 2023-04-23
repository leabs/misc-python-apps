
def intro(name):
    print("title: text-based-game")
    print()
    print("You wake up in an empty forest, the sound of birds and tree branches in the wind fill your ears. You look around and see a sword on the ground. You pick it up and look at it. It's a sword of shadows. You look around and see a cave. You walk towards it and enter.")
    print()
    # Ask the user's name
    name = input(str("BTW, what is your name? "))
    print()
    return name

def classSelect():
    # Ask the user what class they want to be
    print("What class do you want to be?")
    print("1. Tank")
    print("2. Warrior")
    print("3. Healer")
    print()
    # Get the user's class choice
    classSelect = input(str("What class do you want to be? "))
    print()
    # If the user chooses mage, assign the mage stats to the player
    if classSelect == "1":
        player = "tank"
        return player


    # If the user chooses warrior, assign the warrior stats to the player
    elif classSelect == "2":
        player = "warrior"
        return player

    # If the user chooses archer, assign the archer stats to the player
    elif classSelect == "3":
        player = "healer"
        return player
