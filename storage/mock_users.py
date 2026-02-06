MOCK_USERS = {
    "mlue": "merepapaindiaha",
    "pulkit": "pass123",
    "umang": "mlue"
}

def validate_user(user_id: str, password: str) -> bool:
    return MOCK_USERS.get(user_id) == password
