import bcrypt

users = [
    {"username": "Dorcas", "password": "Dorcas123"},
    {"username": "Tshepo", "password": "Tshepo123"},
    {"username": "Innocent", "password": "Innocent123"},
    {"username": "Bruce", "password": "Bruce123"},
    {"username": "Penny", "password": "Penny123"},
    {"username": "Francis", "password": "Francis123"}
]

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

hashed_users = [{"username": user["username"], "password": hash_password(user["password"])} for user in users]

import json
with open('users.json', 'w') as file:
    json.dump({"users": hashed_users}, file, indent=4)

print("Users with hashed passwords saved to users.json")
