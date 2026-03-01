import streamlit_authenticator as stauth
credentials = {
    'usernames': {
        'admin': {'password': 'admin123'},
        'user1': {'password': 'qwer4321'}
    }
}
stauth.Hasher.hash_passwords(credentials)
print("Admin hash:", credentials['usernames']['admin']['password'])
print("User1 hash:", credentials['usernames']['user1']['password'])
