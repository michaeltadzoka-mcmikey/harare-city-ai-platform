#!/usr/bin/env python
"""
Create the initial super admin user.
Run after database setup.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from dashboard.extensions import db
from dashboard.models.user import User

def get_password_windows(prompt):
    """Password input for Windows using msvcrt (shows asterisks)."""
    import msvcrt
    print(prompt, end='', flush=True)
    password = []
    while True:
        ch = msvcrt.getch()
        if ch == b'\r':  # Enter key
            print('')
            break
        elif ch == b'\x08':  # Backspace
            if password:
                password.pop()
                print('\b \b', end='', flush=True)
        else:
            try:
                char = ch.decode('utf-8')
                password.append(char)
                print('*', end='', flush=True)
            except UnicodeDecodeError:
                pass
    return ''.join(password)

def get_password_unix(prompt):
    """Password input for Unix using getpass."""
    import getpass
    return getpass.getpass(prompt)

app = create_app()
with app.app_context():
    if User.query.first():
        print("A user already exists. This script is for initial setup only.")
        sys.exit(1)

    print("\n=== Create Super Admin ===\n")
    username = input("Username: ").strip()
    while not username:
        print("Username cannot be empty.")
        username = input("Username: ").strip()

    email = input("Email: ").strip()
    while not email:
        print("Email cannot be empty.")
        email = input("Email: ").strip()

    if os.name == 'nt':
        getpass_func = get_password_windows
        print("\n(Password characters will appear as asterisks)")
    else:
        getpass_func = getpass.getpass
        print("\n(Password characters will not be visible)")

    while True:
        password = getpass_func("Password (min 8 chars): ")
        if len(password) < 8:
            print("Password too short. Minimum 8 characters required.")
            continue
        confirm = getpass_func("Confirm password: ")
        if password != confirm:
            print("Passwords do not match. Please try again.")
            continue
        break

    user = User(
        username=username,
        email=email,
        can_manage_users=True,
        can_manage_knowledge=True,
        active=True
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print(f"\n✅ Super admin '{username}' created successfully.")