from app.security import hash_password


for password in ["admin123", "zhang123", "li123", "wang123", "123456"]:
    print(f"{password}: {hash_password(password)}")
