with open(r"c:\Users\bradr\OneDrive\Documents\GitHub\events-system\frontend\static\css\attendee\components\navbar.css", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "logout" in line.lower():
            print(f"{i}: {line.strip()}")
