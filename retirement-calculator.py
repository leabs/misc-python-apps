import math
from datetime import date
# This program prompts a user for details on their retirement amounts and calculates how long they can spend their money before they run out

# Prompt user for their age and age they want to retire
age = int(input("How old are you? "))
# ERROR CHECK: If age is negative, print error message
if age < 0:
    print("You can't be negative years old!")
    exit()

retire = int(input("What age would you like to retire? "))
# ERROR CHECK: If retire is negative, print error message
if retire < 0:
    print("You can't retire in the past!")
    exit()
years = retire - age
yearsUntil65 = 65 - age

# Calculate retirement year
currentYear = date.today().year
retireYear = currentYear + years

# ERROR CHECK: if years or yearsUntil65 is negative, print error message
if years < 0 or yearsUntil65 < 0:
    print("You can't retire in the past!")
    exit()

# Ask how much they currently have saved, and how much they plan on saving per year
current = float(input("How much do you currently have saved? "))
savings = float(input(
    "How much do you plan to save per year (in 401k, 403b, IRA, or taxable accounts)? "))
# Array of interest rates
interest = [0.04, 0.06, 0.08]
print("\n")
print("Non pension retirement savings:")
print("\n")
# For each interest rate, calculate how much they would have saved
for i in interest:
    # Calculate total with compounding interest using A = P(1 + r/n)^nt
    total = current * (1 + i/1)**(1*years) + savings * \
        ((1 + i/1)**(1*years) - 1) / (i/1)
    roundTotal = round(total)
    # Print how much they would have at the end of the years
    print("You will have $" + str(roundTotal) + " at age " +
          str(retire) + " assuming an average interest rate of " + str(i) + ".")

# Statically sets to 0.08 interest
midTotal = current * (1 + 0.06/1)**(1*years) + \
    savings * ((1 + 0.06/1)**(1*years) - 1) / (0.06/1)
midRoundTotal = round(midTotal)

print("\n")

print("With $" + str(midRoundTotal) + " at age " + str(retire) +
      " assuming an average interest rate of 6%. That means you could withdrawl interest equal to 6% of your total savings each year, or $" + str(round(midRoundTotal * 0.06)) + " per year.")

print("\n")

pension = str(input("Do you have a pension (y/n)? "))
if pension == "y":
    pensionKnown = str(
        input("Do you know how much you'll get per year(y/n)? "))
    if pensionKnown == "y":
        pensionAmount = float(input("How much is your pension yearly? "))
        totalResults = round(pensionAmount + midRoundTotal * 0.08)
        print("You can withdrawl $" + str(totalResults) + " per year.")
    elif pensionKnown == "n":
        pensionYearlyAverage = float(input(
            "Assuming your pension is NYSLRS Tier 6: Take your top 5 earned years, add them up and dvidie by 5. What is that number? "))
        # Ask user for years of service, and calculate pension (less than 20 years, 20 years, or greater than 20 years)
        yearsOfService = int(
            input("How many years of service will you have? "))
        
        # Benefit Reduction if retire before 63
        if retire < 63:
            if retire == 55:
                benefitReduction = 0.52
            elif retire == 56:
                benefitReduction = 0.455
            elif retire == 57:
                benefitReduction = 0.39
            elif retire == 58:
                benefitReduction = 0.325
            elif retire == 59:
                benefitReduction = 0.26
            elif retire == 60:
                benefitReduction = 0.195
            elif retire == 61:
                benefitReduction = 0.13
            elif retire == 62:
                benefitReduction = 0.065
            else:
                benefitReduction = 0

        if yearsOfService < 20:
            pensionAmount = round(pensionYearlyAverage *
                                  0.0166 * yearsOfService)
            print("You can withdrawl $" + str(pensionAmount) + " per year in pension, plus $" + str(round(midRoundTotal * 0.06)) +
                  " per year in retirement interest giving you a yearly total of $" + str(pensionAmount + round(midRoundTotal * 0.06)) + " if you start withdrawing at age 63.")
            if retire < 63:
                print("You input a retirement age under 63, so your pension will be reduced by " + str(benefitReduction * 100) +
                      "%, giving you a yearly total of $" + str(round(pensionAmount * benefitReduction)) + " if you start withdrawing at age " + str(retire) + ".")
        elif yearsOfService == 20:
            pensionAmount = round(pensionYearlyAverage * 0.0175 * yearsOfService)
            print("You can withdrawl $" + str(pensionAmount) + " per year in pension, plus $" + str(round(midRoundTotal * 0.06)) +
                  " per year in retirement interest giving you a yearly total of $" + str(pensionAmount + round(midRoundTotal * 0.06)) + " if you start withdrawing at age 63.")
            if retire < 63:
                print("You input a retirement age under 63, so your pension will be reduced by " + str(benefitReduction * 100) +
                      "%, giving you a yearly total of $" + str(round(pensionAmount * benefitReduction)) + " if you start withdrawing at age " + str(retire) + ".")
        elif yearsOfService > 20:
            pensionAmount = round(20 * pensionYearlyAverage * 0.0175) + \
                round((yearsOfService - 20) * pensionYearlyAverage * 0.02)
            print("You can withdrawl $" + str(pensionAmount) + " per year in pension, plus $" + str(round(midRoundTotal * 0.06)) +
                  " per year in retirement interest giving you a yearly total of $" + str(pensionAmount + round(midRoundTotal * 0.06)) + " if you start withdrawing at age 63.")
            if retire < 63:
                print("You input a retirement age under 63, so your pension will be reduced by " + str(benefitReduction * 100) +
                      "%, giving you a yearly total of $" + str(round(pensionAmount * benefitReduction)) + " if you start withdrawing at age " + str(retire) + ".")

if pension == "n":
    print("You can withdrawl a total from retirement interest and your pension of $" +
          str(round(midRoundTotal * 0.08)) + " per year.")
