import sqlite3

conn = sqlite3.connect('user.db')

with conn:
    conn.execute(
        'create table if not exists users (name text primary key not null unique, hashed_password text not null, phone text not null unique)'
    )
    conn.execute(
        'create table if not exists user_rate (user text, item text, rating num, unique (user, item))'
    )
    conn.execute(
        'create table if not exists user_recommend (name text primary key not null unique, rec_items text)'
    )

