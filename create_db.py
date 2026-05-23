import pymysql

def create_db_if_not_exists():
    try:
        connection = pymysql.connect(
            host='127.0.0.1',
            user='root',
            password='ra02',
            port=3306
        )
        with connection.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS billing_system;")
            print("Database 'billing_system' verified/created successfully in MySQL!")
        connection.close()
    except Exception as e:
        print("Error connecting to MySQL or creating database:", e)

if __name__ == "__main__":
    create_db_if_not_exists()
