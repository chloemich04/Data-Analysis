import matplotlib.pyplot as plt

# WE ARE USING THIS FOR OUR CHARTS!!!!! it's really nice

# Example cumulative data (this isn't real data; it's from chat)
reports = [10, 20, 40, 60, 80, 100]
total_themes = [4, 7, 9, 10, 10, 10]

plt.plot(reports, total_themes, marker='o')
plt.title("Data Saturation Curve: Blackmail Scam Reports")
plt.xlabel("Number of Reports Analyzed")
plt.ylabel("Cumulative Unique Scam Tactics Identified")
plt.grid(True)
plt.show()
