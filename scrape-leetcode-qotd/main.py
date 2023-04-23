from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# Create a new instance of the Firefox driver
driver = webdriver.Firefox()

# Navigate to the LeetCode website
driver.get("https://leetcode.com/problemset/all")

# Wait for the page to load
driver.implicitly_wait(10)

# Find the green circle element using XPath
circle = driver.find_element(By.XPATH, "//td[@class='success calendar-cell']")

# Use an ActionChains object to click on the green circle
action = ActionChains(driver)
action.move_to_element(circle).click().perform()

# Close the browser window
driver.quit()