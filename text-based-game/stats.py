def stats():
    print()
    # Ask the user what their stats are
    print("1. 1")
    print("2. 2")
    print("3. 3")
    print("4. 4")
    print("5. 5")

    # Get the user's strength
    strength = input(str("What is your strength? "))
    return strength

    print()
    # Ask the user what their stats are
    print("What is your dexterity?")
    print("1. 1")
    print("2. 2")
    print("3. 3")
    print("4. 4")
    print("5. 5")

    # Get the user's dex
    dexterity = input(str("What is your dexterity? "))
    return dexterity
    print()

    # Ask the user what their stats are
    print("What is your magic?")
    print("1. 1")
    print("2. 2")
    print("3. 3")
    print("4. 4")
    print("5. 5")

    # Get the user's magic
    magic = input(str("What is your magic? "))
    return magic
    print()

    # Ask the user if they are ok with the stats, if not repeat the process
    print("Are you ok with these stats?")
    print("1. Yes")
    print("2. No")

    # Get the user's answer
    answer = input(str("Are you ok with these stats? "))
    return answer
    print()

    # If the user is ok with the stats, print "Your stats are: "
    if answer == "1":
        print("Your stats are: " + str(strength) + ", " +
              str(dexterity) + ", " + str(magic) + ".")
    # If the user is not ok with the stats, repeat the process
    else:
        stats()
