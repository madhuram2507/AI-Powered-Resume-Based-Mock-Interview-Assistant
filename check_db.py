import sqlite3

conn = sqlite3.connect("ai_interview.db")
cursor = conn.cursor()

print("\nUSERS")
for row in cursor.execute("SELECT * FROM users"):
    print(row)

print("\nSKILLS")
for row in cursor.execute("SELECT * FROM skills"):
    print(row)

print("\nUSER_SKILLS")
for row in cursor.execute("SELECT * FROM user_skills"):
    print(row)

conn.close()
